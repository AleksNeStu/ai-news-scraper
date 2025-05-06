"""
Search module for semantic search of news articles.

This module provides functionality to search for news articles based on natural
language queries, using vector embeddings for semantic similarity matching.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
import re

from src.embedder import ArticleEmbedder
from src.vector_store import get_vector_store, VectorStore

# Configure logging
logger = logging.getLogger(__name__)


class SemanticSearch:
    """Class for performing semantic search on stored news articles."""
    
    def __init__(self, vector_store: Optional[VectorStore] = None, embedder: Optional[ArticleEmbedder] = None):
        """
        Initialize the SemanticSearch.
        
        Args:
            vector_store: Optional vector store instance. If not provided, the default is used.
            embedder: Optional embedder instance. If not provided, a new one is created.
        """
        self.vector_store = vector_store if vector_store else get_vector_store()
        self.embedder = embedder if embedder else ArticleEmbedder()
    
    def search(self, query: str, limit: int = 5, 
               filter_criteria: Optional[Dict[str, Any]] = None,
               offline_mode: bool = False) -> List[Dict[str, Any]]:
        """
        Search for articles semantically similar to the query.
        
        Args:
            query: Natural language query text.
            limit: Maximum number of results to return.
            filter_criteria: Optional criteria to filter results (e.g., by date, source).
            offline_mode: If True, uses text-based search instead of embeddings.
            
        Returns:
            List[Dict[str, Any]]: List of matching articles with similarity scores.
        """
        if offline_mode:
            logger.info(f"Using text-based search for query in offline mode: '{query}'")
            results = self.text_based_search(query, limit=limit)
            
            # Apply filters if provided
            if filter_criteria and results:
                results = self._apply_filters(results, filter_criteria)
                
            return results
            
        try:
            # Generate embedding for the query
            logger.info(f"Creating embedding for query: '{query}'")
            query_embedding = self.embedder.embed_query(query)
            
            # Perform vector search
            logger.info("Searching for similar articles")
            results = self.vector_store.search(query_embedding, limit=limit)
            
            # Apply filters if provided
            if filter_criteria and results:
                results = self._apply_filters(results, filter_criteria)
                
            # Format results
            return self._format_search_results(results, query)
                
        except Exception as e:
            logger.error(f"Error during semantic search: {str(e)}, falling back to text-based search")
            # Fallback to text-based search
            return self.text_based_search(query, limit=limit)
    
    def _apply_filters(self, results: List[Dict[str, Any]], 
                      filter_criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Apply filters to search results.
        
        Args:
            results: List of search results.
            filter_criteria: Criteria to filter results.
            
        Returns:
            List[Dict[str, Any]]: Filtered search results.
        """
        filtered_results = []
        
        # Process each result
        for result in results:
            # Check if result matches all filter criteria
            matches_all = True
            
            for field, value in filter_criteria.items():
                # Handle date range filter differently
                if field == "date_range" and "publish_date" in result:
                    start_date, end_date = value
                    if not (start_date <= result["publish_date"] <= end_date):
                        matches_all = False
                        break
                
                # Handle source domain filter
                elif field == "source_domains" and "source_domain" in result:
                    if result["source_domain"] not in value:
                        matches_all = False
                        break
                
                # Standard field matching
                elif field in result and result[field] != value:
                    matches_all = False
                    break
            
            if matches_all:
                filtered_results.append(result)
        
        return filtered_results

    def _highlight_query_terms(self, text: str, query: str) -> str:
        """
        Highlight query terms in the text.
        
        Args:
            text: Text to highlight terms in.
            query: Search query containing terms to highlight.
            
        Returns:
            str: Text with highlighted terms.
        """
        if not text or not query:
            return text
            
        # Extract meaningful terms from query (ignore common stop words)
        stop_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with", 
                      "about", "of", "by", "is", "are", "was", "were", "be", "been"}
        
        query_terms = [term.lower() for term in query.split() if term.lower() not in stop_words]
        
        # Nothing to highlight
        if not query_terms:
            return text
            
        # Create a regex pattern to find terms
        pattern = r'\b(' + '|'.join(re.escape(term) for term in query_terms) + r')\b'
        
        # Replace matches with highlighted version
        highlighted = re.sub(pattern, r'**\1**', text, flags=re.IGNORECASE)
        
        return highlighted

    def _format_search_results(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Format search results for display.
        
        Args:
            results: List of search results.
            query: Original search query.
            
        Returns:
            List[Dict[str, Any]]: Formatted search results.
        """
        formatted_results = []
        
        for result in results:
            # Create a new result with only the fields we want to display
            formatted = {
                "url": result.get("url", ""),
                "headline": result.get("headline", ""),
                "source_domain": result.get("source_domain", ""),
                "publish_date": result.get("publish_date", ""),
                "similarity_score": result.get("similarity", 0.0),
            }
            
            # Add summary if available
            if "summary" in result:
                # Highlight query terms in summary
                highlighted_summary = self._highlight_query_terms(result["summary"], query)
                formatted["summary"] = highlighted_summary
            
            formatted_results.append(formatted)
        
        return formatted_results

    def search_by_topic(self, topic: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for articles related to a specific topic.
        
        Args:
            topic: Topic to search for.
            limit: Maximum number of results to return.
            
        Returns:
            List[Dict[str, Any]]: List of articles related to the topic.
        """
        # For topic search, we can use a query like "Articles about {topic}"
        query = f"Articles about {topic}"
        return self.search(query, limit=limit)

    def search_by_keywords(self, keywords: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for articles containing specific keywords.
        
        Args:
            keywords: List of keywords to search for.
            limit: Maximum number of results to return.
            
        Returns:
            List[Dict[str, Any]]: List of articles related to the keywords.
        """
        # Join keywords into a query
        query = " ".join(keywords)
        return self.search(query, limit=limit)

    def get_related_articles(self, article_url: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Find articles related to a specific article.
        
        Args:
            article_url: URL of the reference article.
            limit: Maximum number of related articles to return.
            
        Returns:
            List[Dict[str, Any]]: List of related articles.
        """
        try:
            # Get all articles
            all_articles = self.vector_store.get_all_articles()
            
            # Find the reference article
            reference_article = None
            for article in all_articles:
                if article.get("url") == article_url:
                    reference_article = article
                    break
            
            if not reference_article:
                logger.warning(f"Reference article not found: {article_url}")
                return []
            
            # Use the article's embedding as the query
            embedding = reference_article.get("embedding", [])
            if not embedding:
                logger.warning(f"No embedding found for article: {article_url}")
                return []
            
            # Search for similar articles
            results = self.vector_store.search(embedding, limit=limit+1)
            
            # Remove the reference article from results
            results = [r for r in results if r.get("url") != article_url]
            
            # Format results
            return self._format_search_results(results[:limit], "")
            
        except Exception as e:
            logger.error(f"Error finding related articles: {str(e)}")
            return []
    
    def text_based_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Perform text-based search when vector search is not available (offline mode).
        This method uses basic text matching rather than semantic similarity.
        
        Args:
            query: Natural language query text.
            limit: Maximum number of results to return.
            
        Returns:
            List[Dict[str, Any]]: List of matching articles based on text matching.
        """
        try:
            # Get all articles
            all_articles = self.vector_store.get_all_articles()
            if not all_articles:
                logger.warning("No articles found in storage for text search")
                return []
            
            # Extract meaningful terms from query (ignore common stop words)
            stop_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with", 
                        "about", "of", "by", "is", "are", "was", "were", "be", "been"}
            
            query_terms = [term.lower() for term in query.split() if term.lower() not in stop_words]
            
            # Score each article based on term frequency
            scored_articles = []
            for article in all_articles:
                score = 0
                title = article.get("headline", "").lower()
                text = article.get("text", "").lower()
                summary = article.get("summary", "").lower()
                topics = [t.lower() for t in article.get("topics", [])]
                
                # Check for term matches in title (higher weight)
                for term in query_terms:
                    if term in title:
                        score += 3
                    
                    # Check for term matches in text
                    if term in text:
                        score += 1
                    
                    # Check for term matches in summary (higher weight)
                    if term in summary:
                        score += 2
                    
                    # Check for term matches in topics (highest weight)
                    if any(term in topic for topic in topics):
                        score += 4
                
                # Only include articles with at least one match
                if score > 0:
                    article_copy = article.copy()
                    article_copy["similarity"] = score / (len(query_terms) * 4)  # Normalize score
                    scored_articles.append(article_copy)
            
            # Sort by score
            scored_articles.sort(key=lambda x: x["similarity"], reverse=True)
            
            # Return top results
            results = scored_articles[:limit]
            return self._format_search_results(results, query)
            
        except Exception as e:
            logger.error(f"Error during text-based search: {str(e)}")
            return []
