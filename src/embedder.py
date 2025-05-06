"""
Embedder module for generating vector embeddings of news article content.

This module uses OpenAI's embedding models to convert text content into
vector embeddings that can be used for semantic similarity search.
"""

import logging
from typing import Dict, List, Optional, Union, Any

import numpy as np
from openai import OpenAI
from tqdm import tqdm
import time
from src.config import OPENAI_API_KEY, EMBEDDING_MODEL
from src.scraper import ScrapedArticle
from src.summarizer import ArticleSummarizer

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


class ArticleEmbedder:
    """Class for creating embeddings of news articles using OpenAI's embedding models."""
    
    def __init__(self, model: str = EMBEDDING_MODEL):
        """
        Initialize the ArticleEmbedder.
        
        Args:
            model: The OpenAI embedding model to use.
        """
        self.model = model
    
    def create_embedding(self, text: str) -> List[float]:
        """
        Create an embedding for the provided text.
        
        Args:
            text: The text to embed.
            
        Returns:
            List[float]: Vector embedding of the text.
        """
        try:
            # Call the OpenAI API to get the embedding
            response = client.embeddings.create(
                model=self.model,
                input=text
            )
            
            embedding = response.data[0].embedding
            return embedding
            
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            # Return empty embedding as fallback
            return [0.0] * 1536  # Default embedding dimension for text-embedding-ada-002
    
    def embed_article(self, article: ScrapedArticle, 
                      include_summary: bool = False,
                      summary: Optional[str] = None) -> Dict[str, Any]:
        """
        Create embeddings for different components of an article.
        
        Args:
            article: The ScrapedArticle to embed.
            include_summary: Whether to include summary embedding.
            summary: Optional pre-generated summary to embed.
            
        Returns:
            Dict[str, Any]: Dictionary containing article embeddings and metadata.
        """
        try:
            # Prepare text for embedding
            title_text = article.headline.strip()
            content_text = article.text.strip()
            
            # Create combined text for main embedding
            combined_text = f"{title_text}\n\n{content_text}"
            if include_summary and summary:
                combined_text = f"{title_text}\n\n{summary}\n\n{content_text}"
                
            # Limit text length for API constraints (most embedding models have max token limits)
            if len(combined_text) > 8000:
                combined_text = combined_text[:8000]
            
            # Generate embeddings
            embedding = self.create_embedding(combined_text)
            title_embedding = self.create_embedding(title_text)
            
            # Create result dictionary with embeddings and metadata
            result = {
                "id": hash(article.url),  # Create a unique ID based on URL
                "url": article.url,
                "headline": article.headline,
                "source_domain": article.source_domain,
                "publish_date": article.publish_date,
                "embedding": embedding,
                "title_embedding": title_embedding
            }
            
            # Add summary and summary embedding if provided
            if include_summary and summary:
                result["summary"] = summary
                result["summary_embedding"] = self.create_embedding(summary)
                
            return result
            
        except Exception as e:
            logger.error(f"Error embedding article '{article.headline}': {str(e)}")
            return {
                "id": hash(article.url),
                "url": article.url,
                "headline": article.headline,
                "source_domain": article.source_domain,
                "embedding": [0.0] * 1536  # Default embedding dimension
            }
    
    def embed_articles(self, articles: List[ScrapedArticle], 
                      summaries: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """
        Create embeddings for a list of articles.
        
        Args:
            articles: List of ScrapedArticle objects.
            summaries: Optional dictionary mapping article URLs to summaries.
            
        Returns:
            List[Dict[str, Any]]: List of dictionaries containing article embeddings and metadata.
        """
        embedded_articles = []
        
        for article in tqdm(articles, desc="Creating embeddings"):
            # Check if summary is available
            summary = None
            include_summary = False
            
            if summaries and article.url in summaries:
                summary = summaries[article.url]
                include_summary = True
                
            # Create embeddings for the article
            embedded_article = self.embed_article(
                article, 
                include_summary=include_summary,
                summary=summary
            )
            
            embedded_articles.append(embedded_article)
            
        logger.info(f"Created embeddings for {len(embedded_articles)} articles")
        return embedded_articles
        
    def embed_query(self, query: str) -> List[float]:
        """
        Create an embedding for a search query.
        
        Args:
            query: The search query text.
            
        Returns:
            List[float]: Vector embedding of the query.
        """
        return self.create_embedding(query)
    
    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Create an embedding for the given text.
        
        Args:
            text: Text to embed.
            
        Returns:
            Optional[List[float]]: Embedding vector or None if failed.
        """
        if not text:
            logger.warning("Cannot create embedding for empty text")
            return None
            
        # Truncate text if it's too long (most models have token limits)
        max_length = 8000  # Adjust based on model's limitations
        if len(text) > max_length:
            logger.warning(f"Text too long ({len(text)} chars), truncating to {max_length}")
            text = text[:max_length]
            
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                # Try to use the OpenAI API
                response = client.embeddings.create(
                    model=self.model,
                    input=text
                )
                embedding = response.data[0].embedding
                return embedding
            except Exception as e:
                retry_count += 1
                error_code = None
                
                if hasattr(e, "status_code"):
                    error_code = e.status_code
                
                logger.error(f"Error creating embedding: Error code: {error_code} - {str(e)}")
                
                if retry_count < max_retries:
                    logger.info(f"Retrying... ({retry_count}/{max_retries})")
                    time.sleep(2)  # Wait before retry
                else:
                    # After all retries failed, return None
                    return None
