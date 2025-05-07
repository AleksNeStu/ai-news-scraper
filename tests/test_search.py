"""
Unit tests for the search module.
"""

# Import config first to suppress warnings
from src.config import suppress_external_library_warnings
suppress_external_library_warnings()

import unittest
from unittest.mock import patch, MagicMock

import numpy as np

from src.search import SemanticSearchEngine


class TestSemanticSearch(unittest.TestCase):
    """Test the SemanticSearchEngine class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create mock vector store and embedder
        self.mock_vector_store = MagicMock()
        self.mock_embedder = MagicMock()
        
        # Create search instance with mocks
        self.search = SemanticSearchEngine(
            vector_store=self.mock_vector_store,
            embedder=self.mock_embedder
        )
        
        # Sample test data
        self.sample_embedding = np.random.rand(1536).astype(np.float32).tolist()
        self.sample_results = [
            {
                "id": 1,
                "url": "https://example.com/article1",
                "headline": "Test Article 1",
                "summary": "This is a summary of test article 1 with some keywords.",
                "source_domain": "example.com",
                "publish_date": "2023-01-01",
                "similarity": 0.95,
                "embedding": np.random.rand(1536).astype(np.float32).tolist()
            },
            {
                "id": 2,
                "url": "https://example.com/article2",
                "headline": "Test Article 2",
                "summary": "This is a summary of test article 2 with different keywords.",
                "source_domain": "example.com",
                "publish_date": "2023-01-02",
                "similarity": 0.85,
                "embedding": np.random.rand(1536).astype(np.float32).tolist()
            }
        ]
    
    def test_search(self):
        """Test the search functionality."""
        # Configure mocks
        self.mock_embedder.embed_query.return_value = self.sample_embedding
        self.mock_vector_store.search.return_value = self.sample_results
        
        # Call the search method
        query = "test query"
        results = self.search.search(query, limit=2)
        
        # Verify embedder was called with the query
        self.mock_embedder.embed_query.assert_called_once_with(query)
        
        # Verify vector store search was called with the embedding
        self.mock_vector_store.search.assert_called_once_with(self.sample_embedding, limit=2)
        
        # Verify the results were processed correctly
        self.assertEqual(len(results), 2)
        
        # Check that results contain expected fields
        for result in results:
            self.assertIn("url", result)
            self.assertIn("headline", result)
            self.assertIn("similarity_score", result)
            self.assertIn("source_domain", result)
    
    def test_search_with_filters(self):
        """Test searching with filters."""
        # Configure mocks
        self.mock_embedder.embed_query.return_value = self.sample_embedding
        self.mock_vector_store.search.return_value = self.sample_results
        
        # Define filter criteria
        filter_criteria = {
            "source_domains": ["example.com"]
        }
        
        # Call the search method with filters
        query = "test query"
        results = self.search.search(query, limit=2, filter_criteria=filter_criteria)
        
        # Verify the results were filtered correctly
        self.assertEqual(len(results), 2)  # Both articles are from example.com
        
        # Try with a different filter that excludes all results
        filter_criteria = {
            "source_domains": ["otherdomain.com"]
        }
        
        # Configure vector store with the same results
        self.mock_vector_store.search.return_value = self.sample_results
        
        # Call the search method again
        results = self.search._apply_filters(self.sample_results, filter_criteria)
        
        # Verify the results were filtered correctly
        self.assertEqual(len(results), 0)  # No articles from otherdomain.com
    
    def test_highlight_query_terms(self):
        """Test term highlighting functionality."""
        text = "This is an article about artificial intelligence and machine learning."
        query = "artificial intelligence"
        
        highlighted = self.search._highlight_query_terms(text, query)
        
        # Verify that "artificial" and "intelligence" are highlighted
        self.assertIn("**artificial**", highlighted)
        self.assertIn("**intelligence**", highlighted)
        
        # Verify that "machine" and "learning" are not highlighted
        self.assertNotIn("**machine**", highlighted)
        self.assertNotIn("**learning**", highlighted)
    
    def test_search_by_topic(self):
        """Test searching by topic."""
        # Configure mocks
        self.mock_embedder.embed_query.return_value = self.sample_embedding
        self.mock_vector_store.search.return_value = self.sample_results
        
        # Call the search by topic method
        topic = "technology"
        results = self.search.search_by_topic(topic, limit=2)
        
        # Verify that the embedder was called with the expected query
        expected_query = f"Articles about {topic}"
        self.mock_embedder.embed_query.assert_called_once_with(expected_query)
        
        # Verify vector store search was called
        self.mock_vector_store.search.assert_called_once()
        
        # Verify results
        self.assertEqual(len(results), 2)

    def test_get_related_articles(self):
        """Test getting related articles."""
        # Configure mocks
        self.mock_vector_store.get_all_articles.return_value = self.sample_results
        self.mock_vector_store.search.return_value = self.sample_results
        
        # Set up a reference article URL
        reference_url = "https://example.com/article1"
        
        # Call the get related articles method
        results = self.search.get_related_articles(reference_url, limit=1)
        
        # Verify get_all_articles was called
        self.mock_vector_store.get_all_articles.assert_called_once()
        
        # Only the second article should be returned (not the reference article)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://example.com/article2")


if __name__ == '__main__':
    unittest.main()
