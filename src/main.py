"""
Main module for orchestrating the AI News Scraper pipeline.

This module coordinates the entire workflow from scraping articles,
generating summaries, extracting topics, creating embeddings, and
storing them in the vector database.
"""

import argparse
import logging
import sys
import json
from typing import List, Dict, Any, Optional
import time
from dataclasses import asdict

from src.config import validate_config
from src.scraper import ArticleScraper, ScrapedArticle
from src.summarizer import ArticleSummarizer, EnhancedArticleSummarizer
from src.topics import TopicExtractor, EnhancedTopicExtractor
from src.embedder import ArticleEmbedder
from src.vector_store import get_vector_store
from src.search import SemanticSearch


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("news_scraper.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def read_urls_from_file(file_path: str) -> List[str]:
    """
    Read URLs from a text file, ignoring comments and empty lines.
    
    Args:
        file_path: Path to the file containing URLs.
        
    Returns:
        List of URLs.
    """
    urls = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                # Strip whitespace and skip empty lines or comments
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
        logger.info(f"Read {len(urls)} URLs from {file_path}")
        return urls
    except Exception as e:
        logger.error(f"Error reading URLs from file {file_path}: {str(e)}")
        return []


class NewsPipeline:
    """Class for orchestrating the entire news processing pipeline."""
    
    def __init__(self, use_enhanced: bool = False, offline_mode: bool = False):
        """
        Initialize the NewsPipeline.
        
        Args:
            use_enhanced: Whether to use enhanced versions of summarizer and topic extractor.
            offline_mode: Whether to run in offline mode (skip API calls).
        """
        # Save the offline mode setting
        self.offline_mode = offline_mode
        
        # In offline mode, we can skip API config validation
        if not offline_mode and not validate_config():
            raise ValueError("Invalid configuration. Please check your .env file.")
            
        # Initialize components
        self.scraper = ArticleScraper()
        
        if use_enhanced and not offline_mode:
            self.summarizer = EnhancedArticleSummarizer()
            self.topic_extractor = EnhancedTopicExtractor()
        else:
            self.summarizer = ArticleSummarizer()
            self.topic_extractor = TopicExtractor()
            
        self.embedder = ArticleEmbedder()
        self.vector_store = get_vector_store()
        self.search = SemanticSearch(vector_store=self.vector_store, embedder=self.embedder)
        
        logger.info(f"News pipeline initialized (offline mode: {offline_mode})")
    
    def process_urls(self, urls: List[str]) -> Dict[str, Any]:
        """
        Process a list of URLs through the entire pipeline.
        
        Args:
            urls: List of URLs to process.
            
        Returns:
            Dict[str, Any]: Results of the processing.
        """
        start_time = time.time()
        
        # Step 1: Scrape articles
        logger.info(f"Scraping {len(urls)} articles")
        articles = self.scraper.scrape_urls(urls)
        logger.info(f"Successfully scraped {len(articles)} articles")
        
        if not articles:
            logger.error("No articles were scraped. Aborting pipeline.")
            return {"error": "No articles were scraped", "urls": urls}
        
        # Check if running in offline mode
        if self.offline_mode:
            logger.info("Running in offline mode - skipping API calls for summarization, topic extraction, and embedding")
            
            # Create basic entries without using external APIs
            articles_data = []
            for article in articles:
                # Extract keywords from the text as basic topics
                basic_topics = self._extract_basic_topics(article.text)
                
                # Create a basic summary from the first few paragraphs
                basic_summary = self._create_basic_summary(article.text)
                
                article_data = {
                    "url": article.url,
                    "headline": article.headline,
                    "text": article.text[:2000] + "..." if len(article.text) > 2000 else article.text,
                    "summary": basic_summary,
                    "topics": basic_topics,
                    "source_domain": article.source_domain,
                    "publish_date": article.publish_date,
                    "authors": article.authors,
                    "offline_processed": True
                }
                articles_data.append(article_data)
            
            # Store the articles without embeddings
            logger.info("Storing articles without embeddings (offline mode)")
            success = self.vector_store.store_articles_without_embeddings(articles_data)
            
            # Prepare results
            elapsed_time = time.time() - start_time
            
            results = {
                "processed_count": len(articles),
                "total_urls": len(urls),
                "elapsed_seconds": elapsed_time,
                "success": success,
                "mode": "offline"
            }
            
            logger.info(f"Offline pipeline completed in {elapsed_time:.2f} seconds")
            return results
        
        # Standard online processing path
        # Step 2: Generate summaries
        logger.info("Generating summaries")
        summaries = {}
        try:
            summaries = self.summarizer.summarize_articles(articles)
            if not summaries:
                logger.warning("Failed to generate any summaries. Using article titles as fallback.")
        except Exception as e:
            logger.error(f"Error during summarization: {str(e)}")
            logger.info("Using article titles as fallback summaries")
        
        # Use fallback summaries if needed
        if not summaries:
            summaries = {article.url: f"Summary unavailable: {article.headline}" for article in articles}
        
        # Step 3: Extract topics
        logger.info("Extracting topics")
        article_topics = {}
        try:
            article_topics = self.topic_extractor.extract_topics_for_articles(articles)
            if not article_topics:
                logger.warning("Failed to extract topics. Using fallback topics.")
        except Exception as e:
            logger.error(f"Error during topic extraction: {str(e)}")
            logger.info("Using fallback topics")
        
        # Use fallback topics if needed
        if not article_topics:
            article_topics = {article.url: ["news", "article"] for article in articles}
        
        # Step 4: Create embeddings
        logger.info("Creating embeddings")
        try:
            embedded_articles = self.embedder.embed_articles(articles, summaries=summaries)
            
            # Add topics to embedded articles
            for article_data in embedded_articles:
                url = article_data.get("url")
                if url in article_topics:
                    article_data["topics"] = article_topics[url]
            
            # Step 5: Store in vector database
            logger.info("Storing embeddings in vector database")
            success = self.vector_store.store_embeddings(embedded_articles)
            
            if not success:
                logger.error("Failed to store embeddings in vector database")
        except Exception as e:
            logger.error(f"Error during embedding or storage: {str(e)}")
            success = False
            
            # Create basic entries without embeddings if API fails
            embedded_articles = []
            for article in articles:
                article_data = {
                    "url": article.url,
                    "headline": article.headline,
                    "text": article.text[:1000] + "..." if len(article.text) > 1000 else article.text,
                    "summary": summaries.get(article.url, "Summary unavailable"),
                    "topics": article_topics.get(article.url, ["news", "article"]),
                    "embedding_error": "API authentication failed. Using text-only storage."
                }
                embedded_articles.append(article_data)
            
            # Try to store the articles without embeddings
            try:
                success = self.vector_store.store_articles_without_embeddings(embedded_articles)
            except Exception as ex:
                logger.error(f"Failed to store articles without embeddings: {str(ex)}")
                success = False
        
        # Prepare results
        elapsed_time = time.time() - start_time
        
        results = {
            "processed_count": len(articles),
            "total_urls": len(urls),
            "elapsed_seconds": elapsed_time,
            "success": success,
            "mode": "online"
        }
        
        logger.info(f"Pipeline completed in {elapsed_time:.2f} seconds")
        return results
    
    def search_articles(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for articles using the semantic search.
        
        Args:
            query: Search query.
            limit: Maximum number of results to return.
            
        Returns:
            List[Dict[str, Any]]: Search results.
        """
        logger.info(f"Searching for: '{query}'")
        
        if self.offline_mode:
            logger.info("Using text-based search in offline mode")
            results = self.search.search(query, limit=limit, offline_mode=True)
        else:
            results = self.search.search(query, limit=limit)
            
        logger.info(f"Found {len(results)} matching articles")
        return results
    
    def get_all_articles(self) -> List[Dict[str, Any]]:
        """
        Get all articles stored in the vector database.
        
        Returns:
            List[Dict[str, Any]]: All stored articles.
        """
        return self.vector_store.get_all_articles()
    
    def clear_database(self) -> bool:
        """
        Clear the vector database.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        return self.vector_store.clear()
    
    def _extract_basic_topics(self, text: str, max_topics: int = 5) -> List[str]:
        """
        Extract basic topics from text using frequency analysis (no API calls).
        
        Args:
            text: Article text to analyze.
            max_topics: Maximum number of topics to extract.
            
        Returns:
            List of extracted topics.
        """
        # Define common stop words to filter out
        stop_words = {
            "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", 
            "are", "as", "at", "be", "because", "been", "before", "being", "below", "between", 
            "both", "but", "by", "could", "did", "do", "does", "doing", "down", "during", "each", 
            "few", "for", "from", "further", "had", "has", "have", "having", "he", "he'd", "he'll", 
            "he's", "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", 
            "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "it", "it's", "its", 
            "itself", "let's", "me", "more", "most", "my", "myself", "nor", "of", "on", "once", "only", 
            "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", 
            "she'd", "she'll", "she's", "should", "so", "some", "such", "than", "that", "that's", 
            "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these", 
            "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", 
            "too", "under", "until", "up", "very", "was", "we", "we'd", "we'll", "we're", "we've", 
            "were", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", 
            "who's", "whom", "why", "why's", "with", "would", "you", "you'd", "you'll", "you're", "you've", 
            "your", "yours", "yourself", "yourselves", "said", "says", "also", "like", "just", "now"
        }
        
        try:
            # Tokenize the text
            text = text.lower()
            
            # Remove punctuation
            import re
            text = re.sub(r'[^\w\s]', ' ', text)
            
            # Split into words
            words = text.split()
            
            # Filter out stop words and short words
            filtered_words = [word for word in words if word not in stop_words and len(word) > 3]
            
            # Count word frequencies
            from collections import Counter
            word_counts = Counter(filtered_words)
            
            # Get the most common words
            common_words = word_counts.most_common(max_topics)
            
            # Return just the words
            return [word for word, _ in common_words] if common_words else ["news", "article"]
            
        except Exception as e:
            logger.error(f"Error extracting basic topics: {str(e)}")
            return ["news", "article"]
            
    def _create_basic_summary(self, text: str, max_length: int = 200) -> str:
        """
        Create a basic summary from article text (no API calls).
        
        Args:
            text: Article text to summarize.
            max_length: Maximum length of the summary in characters.
            
        Returns:
            Basic summary string.
        """
        try:
            # Split the text into paragraphs
            paragraphs = text.split('\n\n')
            
            # Use the first paragraph(s) as a summary
            summary = ""
            for para in paragraphs:
                # Skip very short paragraphs
                if len(para.strip()) < 40:
                    continue
                    
                # Add paragraph to summary
                if len(summary) > 0:
                    summary += " "
                summary += para.strip()
                
                # Stop if we've reached the maximum length
                if len(summary) >= max_length:
                    break
                    
            # Truncate if needed and add ellipsis
            if len(summary) > max_length:
                summary = summary[:max_length].strip() + "..."
                
            return summary if summary else "Summary unavailable"
            
        except Exception as e:
            logger.error(f"Error creating basic summary: {str(e)}")
            return "Summary unavailable"
    

def main():
    """Main entry point for the command line interface."""
    parser = argparse.ArgumentParser(description="AI News Scraper and Semantic Search")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Process URLs command
    process_parser = subparsers.add_parser("process", help="Process URLs")
    
    # Create a mutually exclusive group for URL input methods
    url_group = process_parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument("--urls", nargs="+", help="URLs to process (space-separated)")
    url_group.add_argument("--file", type=str, help="Path to file containing URLs (one per line)")
    
    process_parser.add_argument("--enhanced", action="store_true", help="Use enhanced processing")
    process_parser.add_argument("--offline", action="store_true", 
                               help="Run in offline mode (skip API calls, use basic processing)")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search articles")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=5, help="Maximum number of results")
    search_parser.add_argument("--offline", action="store_true",
                              help="Run in offline mode (use text search instead of embeddings)")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all articles")
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear the vector database")
    
    # Parse arguments
    args = parser.parse_args()
    
    if args.command == "process":
        urls = []
        if args.urls:
            urls = args.urls
        elif args.file:
            urls = read_urls_from_file(args.file)
        
        if not urls:
            logger.error("No URLs to process. Please provide URLs or a valid file.")
            return
        
        # Create pipeline with appropriate settings
        pipeline = NewsPipeline(use_enhanced=args.enhanced, offline_mode=args.offline)
        logger.info(f"Running pipeline with {'offline' if args.offline else 'online'} mode")
        
        # Process the URLs
        results = pipeline.process_urls(urls)
        print(json.dumps(results, indent=2))
        
    elif args.command == "search":
        pipeline = NewsPipeline(offline_mode=args.offline)
        results = pipeline.search_articles(args.query, limit=args.limit)
        print(json.dumps(results, indent=2))
        
    elif args.command == "list":
        pipeline = NewsPipeline()
        articles = pipeline.get_all_articles()
        print(json.dumps(articles, indent=2))
        
    elif args.command == "clear":
        pipeline = NewsPipeline()
        success = pipeline.clear_database()
        print(f"Database cleared: {success}")
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
