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
        
        # Sample results with payload structure (as used by some vector DB implementations)
        self.payload_results = [
            {
                "id": "1",
                "score": 0.92,
                "payload": {
                    "url": "https://example.com/article1",
                    "headline": "Test Article 1",
                    "summary": "This is a summary of test article 1 with some keywords.",
                    "source_domain": "example.com",
                    "publish_date": "2023-01-01",
                    "topics": ["AI", "Technology"]
                }
            },
            {
                "id": "2",
                "score": 0.83,
                "payload": {
                    "url": "https://example.com/article2",
                    "headline": "Test Article 2", 
                    "summary": "This is a summary of test article 2 with different keywords.",
                    "source_domain": "example.com",
                    "publish_date": "2023-01-02",
                    "topics": ["Machine Learning", "Data Science"]
                }
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
        
    def test_hybrid_search(self):
        """Test hybrid search functionality combining semantic and text search."""
        # Configure mocks
        self.mock_embedder.embed_query.return_value = self.sample_embedding
        self.mock_vector_store.search.return_value = self.sample_results
        self.mock_vector_store.get_all_metadata.return_value = self.sample_results
        
        # Set up a sample query
        query = "artificial intelligence"
        
        # Mock both search methods to test the hybrid search
        with patch.object(self.search, 'search', return_value=self.sample_results) as mock_semantic_search:
            with patch.object(self.search, 'text_search', return_value=self.sample_results) as mock_text_search:
                
                # Call the hybrid search method
                results = self.search.hybrid_search(query, limit=2, blend=0.6)
                
                # Verify both search methods were called
                mock_semantic_search.assert_called_once()
                mock_text_search.assert_called_once()
                
                # Verify the results
                self.assertEqual(len(results), 2)
                
                # Check that results contain both semantic and text scores
                for result in results:
                    self.assertIn("semantic_score", result)
                    self.assertIn("text_score", result)
                    self.assertIn("similarity", result)
                    
                # Verify the blend factor is applied correctly
                # The hybrid score should be a weighted average of the semantic and text scores
                if len(results) > 0:
                    result = results[0]
                    expected_score = 0.6 * result["semantic_score"] + 0.4 * result["text_score"]
                    self.assertAlmostEqual(result["similarity"], expected_score, places=5)
    
    def test_search_fallback_when_embedding_fails(self):
        """Test fallback to text search when embedding generation fails."""
        # Configure the embedder to return None (failed embedding)
        self.mock_embedder.embed_query.return_value = None
        
        # Configure the vector store to return sample results for text search
        self.mock_vector_store.get_all_metadata.return_value = self.sample_results
        
        # Set up a spy on the text_based_search method
        with patch.object(self.search, 'text_based_search', return_value=self.sample_results) as mock_text_search:
            
            # Call the search method
            query = "test query"
            results = self.search.search(query, limit=2)
            
            # Verify that the text-based search was called as fallback
            mock_text_search.assert_called_once()
            
            # Verify results were returned
            self.assertEqual(len(results), 2)
    
    def test_search_with_exception(self):
        """Test search handling when an exception occurs during semantic search."""
        # Configure the embedder to raise an exception
        self.mock_embedder.embed_query.side_effect = Exception("Simulated embedding error")
        
        # Configure the vector store for the text-based fallback
        self.mock_vector_store.get_all_metadata.return_value = self.sample_results
        
        # Call the search method
        query = "test query"
        results = self.search.search(query, limit=2)
        
        # Verify that we got results from the fallback mechanism
        self.assertEqual(len(results), 2)
        
        # Reset the side effect
        self.mock_embedder.embed_query.side_effect = None
    
    def test_format_search_results_with_payload(self):
        """Test formatting results with 'payload' structure."""
        # Set up query
        query = "artificial intelligence"
        
        # Call the _format_search_results method directly with payload-style results
        results = self.search._format_search_results(self.payload_results, query)
        
        # Verify the results were processed correctly
        self.assertEqual(len(results), 2)
        
        # Check that payload fields were extracted correctly
        for i, result in enumerate(results):
            self.assertEqual(result["url"], self.payload_results[i]["payload"]["url"])
            self.assertEqual(result["headline"], self.payload_results[i]["payload"]["headline"])
            self.assertAlmostEqual(result["similarity_score"], self.payload_results[i]["score"])
            # Check that topics were preserved
            self.assertIn("topics", result)
    
    def test_search_with_empty_query(self):
        """Test searching with an empty query."""
        # Configure mocks for text-based search fallback
        self.mock_vector_store.get_all_metadata.return_value = self.sample_results
        
        # Mock the text_based_search method directly to avoid complexity
        with patch.object(self.search, 'text_based_search', return_value=self.sample_results) as mock_text_search:
            # Call the search method with an empty query
            results = self.search.search("   ", limit=2)  # Test with whitespace
            
            # Verify that the embedder was NOT called (used text search directly)
            self.mock_embedder.embed_query.assert_not_called()
    def test_text_based_search(self):
        """Test the text-based search functionality."""
        # Configure mock
        self.mock_vector_store.get_all_metadata.return_value = self.sample_results
        
        # Call the text-based search method
        query = "test article keywords"
        results = self.search.text_based_search(query, limit=2)
        
        # Verify the vector store was queried for metadata
        self.mock_vector_store.get_all_metadata.assert_called_once()
        
        # Verify results were returned and formatted
        self.assertEqual(len(results), 2)
        
        # Check that results have expected fields
        for result in results:
            self.assertIn("url", result)
            self.assertIn("headline", result)
            self.assertIn("similarity_score", result)
            
    def test_search_with_offline_mode(self):
        """Test the search functionality in offline mode."""
        # Configure mock for text-based search
        self.mock_vector_store.get_all_metadata.return_value = self.sample_results
        
        # Call the search method with offline_mode=True
        query = "test query"
        results = self.search.search(query, limit=2, offline_mode=True)
        
        # Verify that embedder was not called (using text-based search instead)
        self.mock_embedder.embed_query.assert_not_called()
        
        # Verify the vector store was queried for metadata directly
        self.mock_vector_store.get_all_metadata.assert_called_once()
        
        # Verify results were returned
        self.assertEqual(len(results), 2)
        
    def test_search_with_date_range_filter(self):
        """Test searching with date range filters."""
        # Configure mocks
        self.mock_embedder.embed_query.return_value = self.sample_embedding
        self.mock_vector_store.search.return_value = self.sample_results
        
        # Define date range filter criteria
        filter_criteria = {
            "date_range": ("2023-01-01", "2023-01-01")  # Only include the first article date
        }
        
        # Call the filter method directly
        results = self.search._apply_filters(self.sample_results, filter_criteria)
        
        # Verify the results were filtered correctly
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://example.com/article1")
        
    def test_format_malformed_results(self):
        """Test handling of malformed results during formatting."""
        # Set up query
        query = "artificial intelligence"
        
        # Create some malformed results
        malformed_results = [
            {},  # Empty result
            {"payload": {}},  # Empty payload
            {"url": "https://example.com/article3"},  # Missing headline
            {"headline": "Test Article 4"},  # Missing URL
            None,  # None result
            # One valid result
            {
                "url": "https://example.com/article5",
                "headline": "Test Article 5",
                "summary": "Valid summary",
                "similarity": 0.75
            }
        ]
        
        # Call the _format_search_results method with malformed results
        results = self.search._format_search_results(malformed_results, query)
        
        # Should only return the valid result
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://example.com/article5")
        self.assertEqual(results[0]["headline"], "Test Article 5")
    
    def test_search_with_empty_text_fields(self):
        """Test searching with articles that have empty text fields."""
        # Configure mocks
        self.mock_embedder.embed_query.return_value = self.sample_embedding
        
        # Create articles with empty fields
        articles_with_empty_fields = [
            {
                "id": 3,
                "url": "https://example.com/article3",
                "headline": "",  # Empty headline
                "summary": "This has a summary but no headline",
                "source_domain": "example.com",
                "similarity": 0.7
            },
            {
                "id": 4,
                "url": "https://example.com/article4",
                "headline": "Article with no summary",
                "summary": "",  # Empty summary
                "source_domain": "example.com",
                "similarity": 0.65
            }
        ]
        
        self.mock_vector_store.search.return_value = articles_with_empty_fields
        
        # Call the search method
        results = self.search.search("test query", limit=2)
        
        # Verify we still get results with empty fields
        self.assertEqual(len(results), 2)
        
        # Check first result has empty headline but is still returned
        self.assertEqual(results[0]["url"], "https://example.com/article3")
        self.assertEqual(results[0]["headline"], "")
        
        # Check second result has empty summary but is still returned
        self.assertEqual(results[1]["url"], "https://example.com/article4")
        self.assertEqual(results[1]["headline"], "Article with no summary")


if __name__ == '__main__':
    unittest.main() mock for text-based search
        self.mock_vector_store.get_all_metadata.return_value = self.sample_results
        
        # Call the search method with offline_mode=True
        query = "test query"
        results = self.search.search(query, limit=2, offline_mode=True)
        
        # Verify that embedder was not called (using text-based search instead)
        self.mock_embedder.embed_query.assert_not_called()
        
        # Verify the vector store was queried for metadata directly
        self.mock_vector_store.get_all_metadata.assert_called_once()
        
        # Verify results were returned
        self.assertEqual(len(results), 2)
        
        # Check that results have expected fields
        for result in results:
            self.assertIn("url", result)
            self.assertIn("headline", result)
    
    def test_search_with_date_range_filter(self):
        """Test searching with date range filters."""
        # Configure mocks
        self.mock_embedder.embed_query.return_value = self.sample_embedding
        self.mock_vector_store.search.return_value = self.sample_results
        
        # Define date range filter criteria
        filter_criteria = {
            "date_range": ("2023-01-01", "2023-01-01")  # Only include the first article date
        }
        
        # Call the filter method directly
        results = self.search._apply_filters(self.sample_results, filter_criteria)
        
        # Verify the results were filtered correctly
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://example.com/article1")
    
    def test_search_with_invalid_filter(self):
        """Test searching with invalid filter criteria."""
        # Configure mocks
        self.mock_embedder.embed_query.return_value = self.sample_embedding
        self.mock_vector_store.search.return_value = self.sample_results
        
        # Define an invalid filter
        filter_criteria = {
            "nonexistent_field": "some value"
        }
        
        # Call the search method with the invalid filter
        results = self.search.search("test query", limit=2, filter_criteria=filter_criteria)
        
        # Should return all results since the filter doesn't apply to any field
        self.assertEqual(len(results), 2)
    
    def test_format_malformed_results(self):
        """Test handling of malformed results during formatting."""
        # Set up query
        query = "artificial intelligence"
        
        # Create some malformed results
        malformed_results = [
            {},  # Empty result
            {"payload": {}},  # Empty payload
            {"url": "https://example.com/article3"},  # Missing headline
            {"headline": "Test Article 4"},  # Missing URL
            None,  # None result
            # One valid result
            {
                "url": "https://example.com/article5",
                "headline": "Test Article 5",
                "summary": "Valid summary",
                "similarity": 0.75
            }
        ]
        
        # Call the _format_search_results method with malformed results
        results = self.search._format_search_results(malformed_results, query)
        
        # Should only return the valid result
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://example.com/article5")
        self.assertEqual(results[0]["headline"], "Test Article 5")
    
    def test_calculate_text_relevance(self):
        """Test the text relevance calculation for text search."""
        # Create a sample article with text content
        article = {
            "headline": "Artificial Intelligence and Machine Learning",
            "text": "This is a detailed article about AI and ML technologies.",
            "summary": "A summary about artificial intelligence applications.",
            "topics": ["AI", "Machine Learning", "Technology"]
        }
        
        # Test with matching query tokens
        query_tokens = ["artificial", "intelligence"]
        relevance = self.search._calculate_text_relevance(article, query_tokens)
        
        # Should have high relevance since query terms appear in headline, summary and topics
        self.assertGreater(relevance, 0.5)
        
        # Test with non-matching query tokens
        query_tokens = ["blockchain", "cryptocurrency"]
        relevance = self.search._calculate_text_relevance(article, query_tokens)
        
        # Should have zero relevance since query terms don't appear in the article
        self.assertEqual(relevance, 0.0)


if __name__ == '__main__':
    unittest.main()
        # Verify results were returned and formatted
        self.assertEqual(len(results), 2)
        
        # Check that results have expected fields
        for result in results:
            self.assertIn("url", result)
            self.assertIn("headline", result)
            self.assertIn("similarity_score", result)
    
    def test_search_with_offline_mode(self):
        """Test the search functionality in offline mode."""
        # Configure mock for text-based search
        self.mock_vector_store.get_all_metadata.return_value = self.sample_results
        
        # Call the search method with offline_mode=True
        query = "test query"
        results = self.search.search(query, limit=2, offline_mode=True)
        
        # Verify that embedder was not called (using text-based search instead)
        self.mock_embedder.embed_query.assert_not_called()
        
        # Verify the vector store was queried for metadata directly
        self.mock_vector_store.get_all_metadata.assert_called_once()
        
        # Verify results were returned
        self.assertEqual(len(results), 2)
        
        # Check that results have expected fields
        for result in results:
            self.assertIn("url", result)
            self.assertIn("headline", result)
    
    def test_search_with_date_range_filter(self):
        """Test searching with date range filters."""
        # Configure mocks
        self.mock_embedder.embed_query.return_value = self.sample_embedding
        self.mock_vector_store.search.return_value = self.sample_results
        
        # Define date range filter criteria
        filter_criteria = {
            "date_range": ("2023-01-01", "2023-01-01")  # Only include the first article date
        }
        
        # Call the filter method directly
        results = self.search._apply_filters(self.sample_results, filter_criteria)
        
        # Verify the results were filtered correctly
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://example.com/article1")
    
    def test_search_with_invalid_filter(self):
        """Test searching with invalid filter criteria."""
        # Configure mocks
        self.mock_embedder.embed_query.return_value = self.sample_embedding
        self.mock_vector_store.search.return_value = self.sample_results
        
        # Define an invalid filter
        filter_criteria = {
            "nonexistent_field": "some value"
        }
        
        # Call the search method with the invalid filter
        results = self.search.search("test query", limit=2, filter_criteria=filter_criteria)
        
        # Should return all results since the filter doesn't apply to any field
        self.assertEqual(len(results), 2)
    
    def test_format_malformed_results(self):
        """Test handling of malformed results during formatting."""
        # Set up query
        query = "artificial intelligence"
        
        # Create some malformed results
        malformed_results = [
            {},  # Empty result
            {"payload": {}},  # Empty payload
            {"url": "https://example.com/article3"},  # Missing headline
            {"headline": "Test Article 4"},  # Missing URL
            None,  # None result
            # One valid result
            {
                "url": "https://example.com/article5",
                "headline": "Test Article 5",
                "summary": "Valid summary",
                "similarity": 0.75
            }
        ]
        
        # Call the _format_search_results method with malformed results
        results = self.search._format_search_results(malformed_results, query)
        
        # Should only return the valid result
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://example.com/article5")
        self.assertEqual(results[0]["headline"], "Test Article 5")
    
    def test_calculate_text_relevance(self):
        """Test the text relevance calculation for text search."""
        # Create a sample article with text content
        article = {
            "headline": "Artificial Intelligence and Machine Learning",
            "text": "This is a detailed article about AI and ML technologies.",
            "summary": "A summary about artificial intelligence applications.",
            "topics": ["AI", "Machine Learning", "Technology"]
        }
        
        # Test with matching query tokens
        query_tokens = ["artificial", "intelligence"]
        relevance = self.search._calculate_text_relevance(article, query_tokens)
        
        # Should have high relevance since query terms appear in headline, summary and topics
        self.assertGreater(relevance, 0.5)
        
        # Test with non-matching query tokens
        query_tokens = ["blockchain", "cryptocurrency"]
        relevance = self.search._calculate_text_relevance(article, query_tokens)
        
        # Should have zero relevance since query terms don't appear in the article
        self.assertEqual(relevance, 0.0)


if __name__ == '__main__':
    unittest.main()
