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
import re
from typing import List, Dict, Any, Optional
import time
from dataclasses import asdict
from pathlib import Path

from src.config import Config, suppress_external_library_warnings
from src.scraper import ArticleScraper, ScrapedArticle
from src.summarizer import ArticleSummarizer, EnhancedArticleSummarizer
from src.topics import TopicExtractor, EnhancedTopicExtractor
from src.embedder import ArticleEmbedder
from src.vector_store import VectorStore, get_vector_store
from src.search import SemanticSearchEngine


# Suppress warnings from external libraries
suppress_external_library_warnings()

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


class NewsScraperPipeline:
    """Class for orchestrating the entire news processing pipeline."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the NewsScraperPipeline.
        
        Args:
            config: Configuration object. If None, a default configuration is used.
        """
        # Initialize configuration
        self.config = config if config else Config()
        self.offline_mode = self.config.offline_mode
        
        # Initialize components
        self.scraper = ArticleScraper(max_retries=self.config.max_retry_attempts)
        self.summarizer = ArticleSummarizer(offline_mode=self.offline_mode)
        self.topic_extractor = TopicExtractor(offline_mode=self.offline_mode)
        self.embedder = ArticleEmbedder(offline_mode=self.offline_mode)
        self.vector_store = get_vector_store()
        self.search_engine = SemanticSearchEngine(vector_store=self.vector_store, embedder=self.embedder)
        
        logger.info(f"News pipeline initialized (offline mode: {self.offline_mode})")
    
    def set_offline_mode(self, offline_mode: bool):
        """
        Set whether the pipeline should run in offline mode.
        
        Args:
            offline_mode: Whether to use offline mode.
        """
        self.offline_mode = offline_mode
        self.config.offline_mode = offline_mode
        
        # Update all components with new mode
        self.summarizer.offline_mode = offline_mode
        self.topic_extractor.offline_mode = offline_mode
        self.embedder.set_offline_mode(offline_mode)
        
        logger.info(f"Pipeline offline mode set to: {offline_mode}")
    
    def process_url(self, url: str, summarize: bool = True, extract_topics: bool = True) -> Dict[str, Any]:
        """
        Process a single URL through the pipeline.
        
        Args:
            url: URL to process.
            summarize: Whether to generate a summary.
            extract_topics: Whether to extract topics.
            
        Returns:
            Dict[str, Any]: Results of the processing.
        """
        try:
            # Step 1: Scrape the article
            article = self.scraper.scrape_url(url)
            if not article:
                logger.warning(f"Failed to scrape article from {url}")
                return {"url": url, "status": "failed", "reason": "Scraping failed"}
            
            # Ensure we have valid text content
            if not article.text or not article.text.strip():
                article.text = f"No text content could be extracted from {url}."
                logger.warning(f"No text content extracted from {url}")
                
            result = {
                "url": url,
                "headline": article.headline or "Untitled Article",  # Ensure headline is not empty
                "source_domain": article.source_domain or "Unknown Domain",
                "publish_date": article.publish_date,
                "status": "success",
                "timestamp": int(time.time())  # Add a timestamp if none exists
            }
            
            # Step 2: Summarize if requested
            if summarize:
                try:
                    summary = self.summarizer.summarize(article)
                    result["summary"] = summary if summary and summary.strip() else "No summary available."
                except Exception as e:
                    logger.error(f"Error generating summary for {url}: {str(e)}")
                    result["summary"] = "Error generating summary."
                    result["summary_error"] = str(e)
            else:
                # Add a default summary even if not requested
                result["summary"] = "Summary generation was not requested."
            
            # Step 3: Extract topics if requested
            if extract_topics:
                try:
                    topics = self.topic_extractor.extract_topics(article)
                    # Ensure we have at least one topic
                    result["topics"] = topics if topics and len(topics) > 0 else ["Uncategorized"]
                except Exception as e:
                    logger.error(f"Error extracting topics for {url}: {str(e)}")
                    result["topics"] = ["Uncategorized"]
                    result["topics_error"] = str(e)
            else:
                # Add default topics if extraction was not requested
                result["topics"] = ["Uncategorized"]
            
            # Step 4: Generate embeddings and store in vector database
            try:
                # Create embeddings
                embedded_article = self.embedder.embed_article(
                    article,
                    include_summary=summarize and "summary" in result,
                    summary=result.get("summary")
                )
                
                # Add topics to the embedded article (with default if missing)
                if extract_topics and "topics" in result and result["topics"]:
                    embedded_article["topics"] = result["topics"]
                else:
                    # Make sure we always have topics, even if extraction failed
                    embedded_article["topics"] = ["Uncategorized"]
                
                # Add the full text (ensure it's not empty)
                if article.text and article.text.strip():
                    embedded_article["text"] = article.text
                else:
                    embedded_article["text"] = "Full text could not be extracted from this article."
                    
                # Ensure summary is present (with default if missing)
                if summarize and "summary" in result and result["summary"]:
                    embedded_article["summary"] = result["summary"]
                else:
                    embedded_article["summary"] = "No summary available for this article."
                
                # Store in vector database
                self.vector_store.store_embeddings([embedded_article])
                result["stored"] = True
                
            except Exception as e:
                logger.error(f"Error storing article in vector database: {str(e)}")
                result["stored"] = False
                result["error"] = str(e)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            return {"url": url, "status": "failed", "reason": str(e)}
    
    def process_urls(self, urls: List[str], summarize: bool = True, extract_topics: bool = True) -> Dict[str, Any]:
        """
        Process a list of URLs through the entire pipeline.
        
        Args:
            urls: List of URLs to process.
            summarize: Whether to generate summaries.
            extract_topics: Whether to extract topics.
            
        Returns:
            Dict[str, Any]: Results of the processing.
        """
        start_time = time.time()
        results = []
        
        for url in urls:
            result = self.process_url(url, summarize, extract_topics)
            results.append(result)
        
        # Prepare final results
        successful = sum(1 for result in results if result.get("status") == "success")
        failed = len(results) - successful
        
        elapsed_time = time.time() - start_time
        summary = {
            "total": len(urls),
            "successful": successful,
            "failed": failed,
            "elapsed_time_seconds": elapsed_time,
            "offline_mode": self.offline_mode
        }
        
        logger.info(f"Processing completed: {successful} succeeded, {failed} failed, in {elapsed_time:.2f} seconds")
        return {"summary": summary, "results": results}
    
    def get_all_articles(self) -> List[Dict[str, Any]]:
        """
        Retrieve all articles stored in the vector database.
        
        Returns:
            List[Dict[str, Any]]: List of all articles with their metadata.
        """
        try:
            logger.info("Retrieving all articles from the vector store")
            return self.vector_store.get_all_articles()
        except Exception as e:
            logger.error(f"Error retrieving articles: {str(e)}")
            return []
    
    def search_articles(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for articles matching the query.
        
        Args:
            query: Search query text
            limit: Maximum number of results to return
            
        Returns:
            List[Dict[str, Any]]: List of matching articles
        """
        try:
            logger.info(f"Searching for articles matching query: '{query}'")
            return self.search_engine.search(query, limit=limit, offline_mode=self.offline_mode)
        except Exception as e:
            logger.error(f"Error searching for articles: {str(e)}")
            return []
    
    def clear_database(self) -> bool:
        """
        Clear all articles from the vector database.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("Clearing vector database")
            self.vector_store.clear()
            return True
        except Exception as e:
            logger.error(f"Error clearing database: {str(e)}")
            return False
        

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
        pipeline = NewsScraperPipeline(config=Config(offline_mode=args.offline))
        logger.info(f"Running pipeline with {'offline' if args.offline else 'online'} mode")
        
        # Process the URLs
        results = pipeline.process_urls(urls)
        print(json.dumps(results, indent=2))
        
    elif args.command == "search":
        pipeline = NewsScraperPipeline(config=Config(offline_mode=args.offline))
        results = pipeline.search_articles(args.query, limit=args.limit)
        print(json.dumps(results, indent=2))
        
    elif args.command == "list":
        pipeline = NewsScraperPipeline()
        articles = pipeline.get_all_articles()
        print(json.dumps(articles, indent=2))
        
    elif args.command == "clear":
        pipeline = NewsScraperPipeline()
        success = pipeline.clear_database()
        print(f"Database cleared: {success}")
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
