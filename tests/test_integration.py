"""
Integration tests for the AI News Scraper Pipeline.

This test file demonstrates how the different components work together.
It uses mocked external services to avoid actual API calls during testing.
"""

# Import config first to suppress warnings
from src.config import suppress_external_library_warnings
suppress_external_library_warnings()

import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os

from src.main import NewsScraperPipeline
from src.scraper import ScrapedArticle


class TestPipelineIntegration(unittest.TestCase):
    """Integration tests for the complete pipeline."""

    def setUp(self):
        """Set up test environment before each test."""
        # Create temp directory for FAISS index
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            "OPENAI_API_KEY": "mock-api-key",
            "VECTOR_DB_TYPE": "FAISS",
            "FAISS_INDEX_PATH": self.temp_dir
        })
        self.env_patcher.start()
        
        # Mock OpenAI API calls
        self.mock_openai_client_patcher = patch('src.summarizer.client')
        self.mock_embeddings_patcher = patch('src.embedder.client')
        self.mock_openai_client = self.mock_openai_client_patcher.start()
        self.mock_embeddings = self.mock_embeddings_patcher.start()
        
        # Configure mock responses
        self.mock_completion_response = MagicMock()
        self.mock_completion_response.choices = [
            MagicMock(message=MagicMock(content="Mock summary of the article"))
        ]
        self.mock_openai_client.chat.completions.create.return_value = self.mock_completion_response
        
        self.mock_embedding_response = MagicMock()
        self.mock_embedding_data = MagicMock(embedding=[0.1] * 1536)
        self.mock_embedding_response.data = [self.mock_embedding_data]
        self.mock_embeddings.embeddings.create.return_value = self.mock_embedding_response
        
        # Mock article scraper
        self.mock_scraper_patcher = patch('src.main.ArticleScraper')
        self.mock_scraper = self.mock_scraper_patcher.start()
        
        # Sample test data
        self.test_articles = [
            ScrapedArticle(
                url="https://example.com/article1",
                headline="Test Article 1",
                text="This is the content of test article 1",
                source_domain="example.com"
            ),
            ScrapedArticle(
                url="https://example.com/article2",
                headline="Test Article 2",
                text="This is the content of test article 2",
                source_domain="example.com"
            )
        ]
        
        # Configure scraper to return test articles
        self.mock_scraper.return_value.scrape_urls.return_value = self.test_articles
    
    def tearDown(self):
        """Clean up after each test."""
        self.env_patcher.stop()
        self.mock_openai_client_patcher.stop()
        self.mock_embeddings_patcher.stop()
        self.mock_scraper_patcher.stop()
        
        # Clean up temp files
        for f in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, f))
        os.rmdir(self.temp_dir)
    
    @patch('src.scraper.ArticleScraper')
    @patch('src.summarizer.ArticleSummarizer')
    @patch('src.topics.TopicExtractor')
    @patch('src.embedder.ArticleEmbedder')
    @patch('src.vector_store.FAISSVectorStore')  
    @patch('src.search.SemanticSearchEngine')
    def test_end_to_end_pipeline(self, MockSearch, MockStore, MockEmbedder, 
                                MockTopics, MockSummarizer, MockScraper):
        """Test the entire pipeline from scraping to search."""
        # Configure mocks
        mock_scraper = MockScraper.return_value
        mock_store = MockStore.return_value
        mock_search = MockSearch.return_value
        
        # Setup mock articles
        mock_articles = [
            MagicMock(url="https://example.com/article1", headline="Article 1", text="Content 1"),
            MagicMock(url="https://example.com/article2", headline="Article 2", text="Content 2"),
        ]
        mock_scraper.scrape_urls.return_value = mock_articles
        
        # Setup mock search results
        mock_search_results = [
            {"url": "https://example.com/article1", "headline": "Article 1", "similarity": 0.95},
            {"url": "https://example.com/article2", "headline": "Article 2", "similarity": 0.85}
        ]
        mock_search.search.return_value = mock_search_results
        
        # Setup mock store results
        mock_store.store_embeddings.return_value = True
        mock_store.get_all_articles.return_value = mock_search_results.copy()
        mock_store.clear.return_value = True
        
        # Set up a side effect for clear() to empty the results
        def clear_articles():
            mock_store.get_all_articles.return_value = []
            return True
            
        mock_store.clear.side_effect = clear_articles
        
        # Mock the config
        mock_config = MagicMock()
        mock_config.offline_mode = True
        mock_config.max_retry_attempts = 3
        
        # Initialize the pipeline with a mocked embedder to ensure our test doesn't hit real API
        with patch('src.main.get_vector_store', return_value=mock_store), \
             patch('src.main.ArticleScraper', return_value=mock_scraper), \
             patch('src.main.SemanticSearchEngine', return_value=mock_search):
             
            pipeline = NewsScraperPipeline(config=mock_config)  # Use mocked config with offline mode
        
        # Process sample URLs
        urls = ["https://example.com/article1", "https://example.com/article2"]
        result = pipeline.process_urls(urls)
        
        # Verify processing was successful
        self.assertTrue(result["success"])
        self.assertEqual(result["processed_count"], 2)
        
        # Perform a search
        search_results = pipeline.search_articles("test query", limit=2)
        
        # Verify we got search results
        self.assertEqual(len(search_results), 2)
        
        # Get all articles and verify they match
        all_articles = pipeline.get_all_articles()
        self.assertEqual(len(all_articles), 2)
        
        # Clear the database
        clear_result = pipeline.clear_database()
        self.assertTrue(clear_result)
        
        # Verify database is empty
        all_articles = pipeline.get_all_articles()
        self.assertEqual(len(all_articles), 0)
    
    def test_text_search_functionality(self):
        """Test that text search functionality works end-to-end."""
        # Set up mock data
        mock_articles = [
            {"url": "https://example.com/article1", "headline": "Test Article One",
             "summary": "This is a test article about AI technology", "text": "Full text about AI technology",
             "source_domain": "example.com", "publish_date": "2025-05-01"},
            {"url": "https://example.com/article2", "headline": "Test Article Two",
             "summary": "This is another test article about machine learning",
             "text": "Full text about machine learning advances", "source_domain": "example.com",
             "publish_date": "2025-05-02"}
        ]
        
        # Set up mocks
        mock_scraper = MagicMock()
        mock_search = MagicMock()
        mock_store = MagicMock()
        mock_store.get_all_metadata.return_value = mock_articles
        
        # Mock search to return articles based on the query
        def mock_search_function(query, limit=5, **kwargs):
            if "AI" in query:
                return [dict(mock_articles[0], similarity=0.85)]
            elif "machine learning" in query:
                return [dict(mock_articles[1], similarity=0.9)]
            else:
                # Return both with different scores
                return [
                    dict(mock_articles[0], similarity=0.7),
                    dict(mock_articles[1], similarity=0.6)
                ][:limit]
                
        # Mock both search and text_search methods to ensure our test works in any mode
        mock_search.search.side_effect = mock_search_function
        mock_search.text_search.side_effect = mock_search_function
        
        # Mock the config
        mock_config = MagicMock()
        mock_config.offline_mode = True
        
        # Initialize the pipeline with mocks
        with patch('src.main.get_vector_store', return_value=mock_store), \
             patch('src.main.ArticleScraper', return_value=mock_scraper), \
             patch('src.main.SemanticSearchEngine', return_value=mock_search):
             
            # Create pipeline with mocked config for offline mode
            pipeline = NewsScraperPipeline(config=mock_config)
            
            # Test specific text searches
            ai_results = pipeline.search_articles("AI technology", limit=1)
            self.assertEqual(len(ai_results), 1)
            self.assertEqual(ai_results[0]["url"], "https://example.com/article1")
            
            ml_results = pipeline.search_articles("machine learning advances", limit=1)
            self.assertEqual(len(ml_results), 1)
            self.assertEqual(ml_results[0]["url"], "https://example.com/article2")
            
            # Test generic search that should return both articles
            all_results = pipeline.search_articles("technology", limit=2)
            self.assertEqual(len(all_results), 2)


if __name__ == '__main__':
    unittest.main()
