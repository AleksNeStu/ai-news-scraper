"""
Search module for semantic search of news articles.

This module provides functionality to search for news articles based on natural
language queries, using vector embeddings for semantic similarity matching.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
import re
import os
import sys

from src.embedder import ArticleEmbedder
from src.vector_store import get_vector_store, VectorStore

# Configure logging
logger = logging.getLogger(__name__)

# Initialize NLTK resources
def download_nltk_resources():
    """Download required NLTK resources if they don't exist."""
    try:
        import nltk
        
        # Create NLTK data directory in the project if it doesn't exist
        nltk_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nltk_data")
        os.makedirs(nltk_data_dir, exist_ok=True)
        
        # Add the project's NLTK data directory to the search path
        nltk.data.path.append(nltk_data_dir)
        
        # Download necessary resources
        resources = {
            "punkt": "tokenizers/punkt",
            "stopwords": "corpora/stopwords",
            "averaged_perceptron_tagger": "taggers/averaged_perceptron_tagger",
            "punkt_tab": "tokenizers/punkt_tab"
        }
        
        for resource, path in resources.items():
            try:
                nltk.data.find(path)
                logger.debug(f"NLTK resource '{resource}' already exists")
            except LookupError:
                logger.info(f"Downloading NLTK resource '{resource}'")
                nltk.download(resource, download_dir=nltk_data_dir, quiet=True)
                
    except Exception as e:
        logger.error(f"Failed to download NLTK resources: {str(e)}")
        
# Download NLTK resources at module import time
download_nltk_resources()


class SemanticSearchEngine:
    """Class for performing semantic search on stored news articles."""
    
    def __init__(self, vector_store: Optional[VectorStore] = None, embedder: Optional[ArticleEmbedder] = None):
        """
        Initialize the SemanticSearchEngine.
        
        Args:
            vector_store: Optional vector store instance. If not provided, the default is used.
            embedder: Optional embedder instance. If not provided, a new one is created.
        """
        self.vector_store = vector_store if vector_store else get_vector_store()
        self.embedder = embedder if embedder else ArticleEmbedder()
        self._initialize_text_search()
    
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
            
            if not query_embedding:
                logger.warning("Failed to generate embedding for query, falling back to text search")
                return self.text_based_search(query, limit=limit, filter_criteria=filter_criteria)
            
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
            if not result:
                continue
                
            # Handle different result structures (payload vs. direct fields)
            if "payload" in result:
                # New structure with payload
                metadata = result["payload"]
                similarity = result.get("score", result.get("similarity", 0.0))
            else:
                # Old structure with direct fields
                metadata = result
                similarity = result.get("similarity", 0.0)
            
            # Validate that we have the necessary fields
            if not metadata:
                logger.warning(f"Result missing metadata: {result}")
                continue
                
            # Get URL and headline - these are required fields
            url = metadata.get("url", "")
            headline = metadata.get("headline", "")
            
            if not url or not headline:
                logger.warning(f"Result missing URL or headline: {metadata}")
                continue
            
            # Create a new result with only the fields we want to display
            formatted = {
                "url": url,
                "headline": headline,
                "source_domain": metadata.get("source_domain", ""),
                "publish_date": metadata.get("publish_date", ""),
                "similarity_score": float(similarity),
            }
            
            # Add summary if available
            if "payload" in result and "summary" in result["payload"]:
                # Highlight query terms in summary
                summary = result["payload"]["summary"]
                if summary and isinstance(summary, str):
                    highlighted_summary = self._highlight_query_terms(summary, query)
                    formatted["summary"] = highlighted_summary
            elif "summary" in metadata:
                # Highlight query terms in summary
                summary = metadata["summary"]
                if summary and isinstance(summary, str):
                    highlighted_summary = self._highlight_query_terms(summary, query)
                    formatted["summary"] = highlighted_summary
            
            # Add topics if available
            if "topics" in metadata and metadata["topics"]:
                formatted["topics"] = metadata["topics"]
            
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
            # Get all articles with metadata
            all_articles = self.vector_store.get_all_metadata()
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
                # Handle different data structures
                if isinstance(article, dict) and "payload" in article:
                    # New structure with payload
                    metadata = article["payload"]
                else:
                    # Old structure with direct fields
                    metadata = article
                
                score = 0
                
                # Get text fields safely
                title = metadata.get("headline", "")
                text = metadata.get("text", "")
                summary = metadata.get("summary", "")
                topics = metadata.get("topics", [])
                
                # Make sure we have strings, not other data types
                title = str(title).lower() if title else ""
                text = str(text).lower() if text else ""
                summary = str(summary).lower() if summary else ""
                topics = [str(t).lower() for t in topics if t]
                
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
                    # Create a result with just the fields we need
                    result = {
                        "url": metadata.get("url", ""),
                        "headline": metadata.get("headline", ""),
                        "source_domain": metadata.get("source_domain", ""),
                        "publish_date": metadata.get("publish_date", ""),
                        "summary": metadata.get("summary", ""),
                        "topics": metadata.get("topics", []),
                        "similarity": score / (len(query_terms) * 4)  # Normalize score
                    }
                    scored_articles.append(result)
            
            # Sort by score
            scored_articles.sort(key=lambda x: x["similarity"], reverse=True)
            
            # Return top results
            results = scored_articles[:limit]
            return self._format_search_results(results, query)
            
        except Exception as e:
            logger.error(f"Error during text-based search: {str(e)}")
            return []
    
    def _initialize_text_search(self):
        """Initialize components needed for text-based search."""
        try:
            import nltk
            from nltk.tokenize import word_tokenize
            from nltk.corpus import stopwords
            
            # We've already downloaded necessary NLTK data at module import time
            # Just access the resources now
            self.tokenize = word_tokenize
            self.stopwords = set(stopwords.words('english'))
            logger.info("Text search components initialized successfully")
        except Exception as e:
            logger.warning(f"NLTK initialization failed: {str(e)}. Text search will use basic tokenization.")
            # Fallback tokenizer
            self.tokenize = lambda text: text.lower().split()
            self.stopwords = {"a", "an", "the", "and", "or", "but", "in", "on", "at", 
                             "to", "for", "with", "by", "about", "as", "of", "is", 
                             "are", "was", "were", "be", "been", "being", "have", "has"}
    
    def text_search(self, query: str, limit: int = 5, 
                   threshold: float = 0.0, exact_match: bool = False,
                   case_match: bool = False, match_all: bool = False,
                   filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Perform text-based search without using embeddings.
        
        Args:
            query: Text query to search for.
            limit: Maximum number of results to return.
            threshold: Minimum relevance score to include in results (0-1).
            exact_match: If True, search for exact phrases.
            case_match: If True, perform case-sensitive search.
            match_all: If True, require all query terms to be present.
            filter_criteria: Optional criteria to filter results (e.g., by date, source).
            
        Returns:
            List[Dict[str, Any]]: List of matching articles with relevance scores.
        """
        logger.info(f"Performing text-based search for: '{query}'")
        
        # Get all articles from the vector store
        all_articles = self.vector_store.get_all_metadata()
        if not all_articles:
            logger.warning("No articles found in vector store for text search")
            return []
        
        # Apply filters if provided
        if filter_criteria:
            all_articles = self._apply_filters(all_articles, filter_criteria)
            if not all_articles:
                logger.info("No articles remain after applying filters")
                return []
        
        # Tokenize and normalize the query
        query_tokens = self._normalize_text(query)
        if not query_tokens:
            logger.warning("Query produced no meaningful tokens after normalization")
            return []
        
        # Calculate relevance for each article
        results = []
        for article in all_articles:
            score = self._calculate_text_relevance(article, query_tokens)
            
            if score >= threshold:
                # Create a copy of the article with the relevance score
                result = dict(article)
                result['similarity'] = score
                results.append(result)
        
        # Sort by relevance (descending) and limit results
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]
    
    def _normalize_text(self, text: str) -> List[str]:
        """
        Normalize text by tokenizing, lowercasing, and removing stopwords.
        
        Args:
            text: Text to normalize.
            
        Returns:
            List[str]: List of normalized tokens.
        """
        if not text:
            return []
            
        # Tokenize
        tokens = self.tokenize(text.lower())
        
        # Remove stopwords and non-alphabetic tokens
        return [token for token in tokens 
                if token.isalpha() and token not in self.stopwords]
    
    def _calculate_text_relevance(self, article: Dict[str, Any], 
                                 query_tokens: List[str]) -> float:
        """
        Calculate relevance score between article and query.
        
        Args:
            article: Article data.
            query_tokens: Preprocessed query tokens.
            
        Returns:
            float: Relevance score between 0 and 1.
        """
        if not query_tokens:
            return 0.0
        
        # Handle different data structures
        if isinstance(article, dict) and "payload" in article:
            # New structure with payload
            metadata = article["payload"]
        else:
            # Old structure with direct fields
            metadata = article
            
        # Prepare article text fields
        text_fields = []
        
        # Add headline with higher weight
        if 'headline' in metadata and metadata['headline'] and isinstance(metadata['headline'], str):
            headline_tokens = self._normalize_text(metadata['headline'])
            text_fields.extend(headline_tokens * 3)  # Triple weight for headline
        
        # Add summary with medium weight
        if 'summary' in metadata and metadata['summary'] and isinstance(metadata['summary'], str):
            summary_tokens = self._normalize_text(metadata['summary'])
            text_fields.extend(summary_tokens * 2)  # Double weight for summary
        
        # Add topics with high weight
        if 'topics' in metadata and metadata['topics']:
            for topic in metadata['topics']:
                if isinstance(topic, str):
                    topic_tokens = self._normalize_text(topic)
                    text_fields.extend(topic_tokens * 4)  # Quadruple weight for topics
        
        # Add full text with normal weight
        if 'text' in metadata and metadata['text'] and isinstance(metadata['text'], str):
            # Only use first 1000 characters to avoid performance issues
            text_preview = metadata['text'][:1000]
            text_tokens = self._normalize_text(text_preview)
            text_fields.extend(text_tokens)
        
        if not text_fields:
            return 0.0
        
        # Count token matches
        matches = sum(1 for token in query_tokens if token in text_fields)
        
        # Calculate score as ratio of matches to query tokens
        return matches / len(query_tokens)
    
    def hybrid_search(self, query: str, limit: int = 5, 
                     threshold: float = 0.3, blend: float = 0.5,
                     filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining semantic and text-based approaches.
        
        Args:
            query: Query string.
            limit: Maximum number of results to return.
            threshold: Minimum combined score to include in results.
            blend: Blend factor between semantic (1.0) and text-based (0.0).
            filter_criteria: Optional criteria to filter results (e.g., by date, source).
            
        Returns:
            List[Dict[str, Any]]: List of matching articles with combined scores.
        """
        logger.info(f"Performing hybrid search with blend {blend} for: '{query}'")
        
        try:
            # Get semantic search results (no limit since we'll combine and rerank)
            try:
                semantic_results = self.search(query, limit=limit*2, filter_criteria=filter_criteria)
                logger.info(f"Got {len(semantic_results)} semantic search results")
            except Exception as e:
                logger.error(f"Error in semantic search: {str(e)}")
                semantic_results = []
            
            # Get text search results (no limit for same reason)
            try:
                text_results = self.text_search(query, limit=limit*2, filter_criteria=filter_criteria)
                logger.info(f"Got {len(text_results)} text search results")
            except Exception as e:
                logger.error(f"Error in text search: {str(e)}")
                text_results = []
            
            # If both search methods failed, return empty results
            if not semantic_results and not text_results:
                logger.warning("Both semantic and text search failed, returning empty results")
                return []
            
            # Create a mapping of URL to combined result
            combined_results = {}
            
            # Process semantic results
            for result in semantic_results:
                url = result.get('url')
                if url:
                    combined_results[url] = {
                        'article': result,
                        'semantic_score': float(result.get('similarity_score', result.get('similarity', 0.0))),
                        'text_score': 0.0
                    }
            
            # Process text results
            for result in text_results:
                url = result.get('url')
                if url:
                    if url in combined_results:
                        # Update existing entry with text score
                        combined_results[url]['text_score'] = float(result.get('similarity_score', result.get('similarity', 0.0)))
                    else:
                        # Create new entry
                        combined_results[url] = {
                            'article': result,
                            'semantic_score': 0.0,
                            'text_score': float(result.get('similarity_score', result.get('similarity', 0.0)))
                        }
            
            # Calculate combined scores and prepare final results
            final_results = []
            for url, data in combined_results.items():
                # Calculate blended score
                combined_score = (blend * data['semantic_score'] + 
                                (1 - blend) * data['text_score'])
                
                if combined_score >= threshold:
                    result = dict(data['article'])
                    result['similarity'] = float(combined_score)
                    result['semantic_score'] = float(data['semantic_score'])
                    result['text_score'] = float(data['text_score'])
                    final_results.append(result)
            
            # Sort by combined score (descending) and limit results
            final_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
            logger.info(f"Returning {len(final_results[:limit])} hybrid search results")
            return final_results[:limit]
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {str(e)}")
            
            # Try to fall back to text search as a last resort
            try:
                logger.warning("Falling back to pure text search")
                return self.text_based_search(query, limit=limit)
            except Exception as e2:
                logger.error(f"Fallback text search also failed: {str(e2)}")
                return []
