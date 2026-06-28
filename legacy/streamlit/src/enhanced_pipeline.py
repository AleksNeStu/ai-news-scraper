"""
Enhanced version of the news scraper pipeline with advanced summarization and topic extraction.

This module extends the basic pipeline with enhanced GenAI capabilities for more
structured and detailed article analysis.
"""

import logging
from typing import Dict, List, Any, Optional

from src.main import NewsScraperPipeline
from src.config import Config
from src.summarizer import EnhancedArticleSummarizer
from src.topics import EnhancedTopicExtractor
from src.embedder import ArticleEmbedder
from src.vector_store import get_vector_store
from src.search import SemanticSearchEngine
from src.scraper import ScrapedArticle, ArticleScraper

# Configure logging
logger = logging.getLogger(__name__)


class EnhancedNewsScraperPipeline(NewsScraperPipeline):
    """
    Enhanced news scraper pipeline with advanced GenAI capabilities.
    
    This class extends the base pipeline with more advanced summarization and topic
    extraction algorithms that provide structured outputs with more detailed analysis.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the EnhancedNewsScraperPipeline.
        
        Args:
            config: Configuration object. If None, a default configuration is used.
        """
        # Initialize configuration
        super().__init__(config)
        
        # Override basic components with enhanced versions
        self.summarizer = EnhancedArticleSummarizer(offline_mode=self.offline_mode)
        self.topic_extractor = EnhancedTopicExtractor(offline_mode=self.offline_mode)
        
        logger.info("Enhanced news pipeline initialized with advanced GenAI capabilities")
    
    def process_url(self, url: str, summarize: bool = True, extract_topics: bool = True) -> Dict[str, Any]:
        """
        Process a single URL through the enhanced pipeline.
        
        Args:
            url: URL to process.
            summarize: Whether to generate a summary.
            extract_topics: Whether to extract topics.
            
        Returns:
            Dict[str, Any]: Results of the processing with enhanced features.
        """
        # Scrape the article first
        article = self.scraper.scrape_url(url)
        if not article:
            logger.warning(f"Failed to scrape article from {url}")
            return {"url": url, "status": "failed", "reason": "Scraping failed"}
        
        # Delegate to a helper method that works with a scraped article
        return self.process_article(article, summarize, extract_topics)
    
    def process_article(self, article: ScrapedArticle, summarize: bool = True, extract_topics: bool = True) -> Dict[str, Any]:
        """
        Process a scraped article with enhanced features.
        
        Args:
            article: Scraped article to process.
            summarize: Whether to generate a summary.
            extract_topics: Whether to extract topics.
            
        Returns:
            Dict[str, Any]: Enhanced processing results.
        """
        try:
            # Base result dictionary
            result = {
                "url": article.url,
                "headline": article.headline or "Untitled Article",
                "source_domain": article.source_domain or "Unknown Domain",
                "publish_date": article.publish_date,
                "status": "success",
            }
            
            # Step 1: Generate enhanced summary if requested
            if summarize:
                try:
                    # The enhanced summarizer returns a dict with summary and key_points
                    summary_data = self.summarizer.summarize(article)
                    result["summary"] = summary_data.get("summary", "No summary available.")
                    result["key_points"] = summary_data.get("key_points", [])
                except Exception as e:
                    logger.error(f"Error generating enhanced summary for {article.url}: {str(e)}")
                    result["summary"] = "Error generating summary."
                    result["key_points"] = []
            else:
                result["summary"] = "Summary generation was not requested."
                result["key_points"] = []
            
            # Step 2: Extract enhanced topics if requested
            if extract_topics:
                try:
                    # The enhanced topic extractor returns a dict with topics and categories
                    topics_data = self.topic_extractor.extract_topics(article)
                    result["topics"] = topics_data.get("topics", ["Uncategorized"])
                    result["topic_categories"] = topics_data.get("categories", {})
                except Exception as e:
                    logger.error(f"Error extracting enhanced topics for {article.url}: {str(e)}")
                    result["topics"] = ["Uncategorized"]
                    result["topic_categories"] = {}
            else:
                result["topics"] = ["Uncategorized"]
                result["topic_categories"] = {}
            
            # Step 3: Generate embeddings and store in vector database
            try:
                # Create embeddings
                embedded_article = self.embedder.embed_article(
                    article,
                    include_summary=summarize,
                    summary=result.get("summary")
                )
                
                # Add topics and categorizations
                if extract_topics:
                    embedded_article["topics"] = result["topics"]
                    embedded_article["topic_categories"] = result["topic_categories"]
                
                # Add the full text
                embedded_article["text"] = article.text
                
                # Add summary and key points
                if summarize:
                    embedded_article["summary"] = result["summary"]
                    embedded_article["key_points"] = result["key_points"]
                
                # Store in vector database
                self.vector_store.store_embeddings([embedded_article])
                result["stored"] = True
                
            except Exception as e:
                logger.error(f"Error storing enhanced article in vector database: {str(e)}")
                result["stored"] = False
                result["error"] = str(e)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced processing for {article.url}: {str(e)}")
            return {"url": article.url, "status": "failed", "reason": str(e)}
    
    def process_urls(self, urls: List[str], summarize: bool = True, extract_topics: bool = True) -> Dict[str, Any]:
        """
        Process multiple URLs with enhanced features.
        
        Args:
            urls: List of URLs to process.
            summarize: Whether to generate summaries.
            extract_topics: Whether to extract topics.
            
        Returns:
            Dict[str, Any]: Results of the enhanced processing.
        """
        # Leverage the parent implementation but with our overridden process_url method
        return super().process_urls(urls, summarize, extract_topics)
    
    def search_articles(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for articles based on a natural language query with enhanced result formatting.
        
        Args:
            query: Natural language query
            limit: Maximum number of results to return
            
        Returns:
            List[Dict[str, Any]]: Enhanced search results with structured data
        """
        # Use the parent search implementation
        results = super().search_articles(query, limit)
        
        # Log the enhanced search
        logger.info(f"Enhanced search for query: '{query}', returned {len(results)} results")
        
        return results
