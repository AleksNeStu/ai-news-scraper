"""
Integration tests for the AI News Scraper Pipeline.

This test file demonstrates how the different components work together.
It uses mocked external services to avoid actual API calls during testing.
"""

import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os

from src.main import NewsPipeline
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
    
    def test_end_to_end_pipeline(self):
        """Test the entire pipeline from scraping to search."""
        # Initialize the pipeline
        pipeline = NewsPipeline()
        
        # Process sample URLs
        urls = ["https://example.com/article1", "https://example.com/article2"]
        result = pipeline.process_urls(urls)
        
        # Verify processing was successful
        self.assertTrue(result["success"])
        self.assertEqual(result["processed_count"], 2)
        
        # Perform a search
        search_results = pipeline.search_articles("test query")
        
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


if __name__ == '__main__':
    unittest.main()
