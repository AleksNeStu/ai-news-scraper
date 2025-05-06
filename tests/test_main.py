"""
Unit tests for the main module.
"""

import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock

from src.main import NewsPipeline, read_urls_from_file
from src.scraper import ScrapedArticle


class TestReadUrlsFromFile(unittest.TestCase):
    """Tests for the read_urls_from_file function."""
    
    def test_read_urls_from_file(self):
        """Test reading URLs from a file."""
        # Create a temporary file with test data
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write("# This is a comment\n")
            f.write("https://example.com/article1\n")
            f.write("  # This is an indented comment\n")
            f.write("https://example.com/article2\n")
            f.write("\n")  # Empty line
            f.write("  https://example.com/article3  \n")  # With whitespace
            temp_filename = f.name
            
        try:
            # Test reading from file
            urls = read_urls_from_file(temp_filename)
            
            # Check the results
            self.assertEqual(len(urls), 3)
            self.assertEqual(urls[0], "https://example.com/article1")
            self.assertEqual(urls[1], "https://example.com/article2")
            self.assertEqual(urls[2], "https://example.com/article3")
            
        finally:
            # Clean up temporary file
            os.unlink(temp_filename)
    
    def test_read_urls_from_nonexistent_file(self):
        """Test handling of nonexistent files."""
        urls = read_urls_from_file("/path/to/nonexistent/file.txt")
        self.assertEqual(urls, [])


class TestNewsPipeline(unittest.TestCase):
    """Test the NewsPipeline class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Mock the configuration validation
        self.mock_validate_config_patcher = patch('src.main.validate_config')
        self.mock_validate_config = self.mock_validate_config_patcher.start()
        self.mock_validate_config.return_value = True
        
        # Mock the components
        self.mock_scraper_patcher = patch('src.main.ArticleScraper')
        self.mock_summarizer_patcher = patch('src.main.ArticleSummarizer')
        self.mock_topic_extractor_patcher = patch('src.main.TopicExtractor')
        self.mock_embedder_patcher = patch('src.main.ArticleEmbedder')
        self.mock_vector_store_patcher = patch('src.main.get_vector_store')
        self.mock_search_patcher = patch('src.main.SemanticSearch')
        
        # Start all the patches
        self.mock_scraper = self.mock_scraper_patcher.start()
        self.mock_summarizer = self.mock_summarizer_patcher.start()
        self.mock_topic_extractor = self.mock_topic_extractor_patcher.start()
        self.mock_embedder = self.mock_embedder_patcher.start()
        self.mock_vector_store = self.mock_vector_store_patcher.start()
        self.mock_search = self.mock_search_patcher.start()
        
        # Configure the component instances
        self.scraper_instance = MagicMock()
        self.summarizer_instance = MagicMock()
        self.topic_extractor_instance = MagicMock()
        self.embedder_instance = MagicMock()
        self.vector_store_instance = MagicMock()
        self.search_instance = MagicMock()
        
        self.mock_scraper.return_value = self.scraper_instance
        self.mock_summarizer.return_value = self.summarizer_instance
        self.mock_topic_extractor.return_value = self.topic_extractor_instance
        self.mock_embedder.return_value = self.embedder_instance
        self.mock_vector_store.return_value = self.vector_store_instance
        self.mock_search.return_value = self.search_instance
        
        # Create a pipeline instance
        self.pipeline = NewsPipeline()
        
        # Sample test data
        self.test_urls = ["https://example.com/article1", "https://example.com/article2"]
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
    
    def tearDown(self):
        """Clean up after each test."""
        # Stop all the patches
        self.mock_validate_config_patcher.stop()
        self.mock_scraper_patcher.stop()
        self.mock_summarizer_patcher.stop()
        self.mock_topic_extractor_patcher.stop()
        self.mock_embedder_patcher.stop()
        self.mock_vector_store_patcher.stop()
        self.mock_search_patcher.stop()
    
    def test_initialization(self):
        """Test the initialization of the pipeline."""
        # Verify that all components were initialized
        self.mock_scraper.assert_called_once()
        self.mock_summarizer.assert_called_once()
        self.mock_topic_extractor.assert_called_once()
        self.mock_embedder.assert_called_once()
        self.mock_vector_store.assert_called_once()
        self.mock_search.assert_called_once()
    
    def test_process_urls(self):
        """Test processing of URLs."""
        # Configure mock behavior
        self.scraper_instance.scrape_urls.return_value = self.test_articles
        self.summarizer_instance.summarize_articles.return_value = {
            "https://example.com/article1": "Summary 1",
            "https://example.com/article2": "Summary 2"
        }
        self.topic_extractor_instance.extract_topics_for_articles.return_value = {
            "https://example.com/article1": ["topic1", "topic2"],
            "https://example.com/article2": ["topic2", "topic3"]
        }
        self.embedder_instance.embed_articles.return_value = [
            {"url": "https://example.com/article1", "embedding": [0.1, 0.2]},
            {"url": "https://example.com/article2", "embedding": [0.3, 0.4]},
        ]
        self.vector_store_instance.store_embeddings.return_value = True
        
        # Process the URLs
        result = self.pipeline.process_urls(self.test_urls)
        
        # Verify each step of the pipeline was called
        self.scraper_instance.scrape_urls.assert_called_once_with(self.test_urls)
        self.summarizer_instance.summarize_articles.assert_called_once_with(self.test_articles)
        self.topic_extractor_instance.extract_topics_for_articles.assert_called_once_with(self.test_articles)
        
        # Check the result
        self.assertTrue(result["success"])
        self.assertEqual(result["processed_count"], len(self.test_articles))
        self.assertEqual(result["total_urls"], len(self.test_urls))
    
    def test_search_articles(self):
        """Test searching for articles."""
        # Configure mock behavior
        self.search_instance.search.return_value = [
            {"url": "https://example.com/article1", "headline": "Test Article 1", "similarity_score": 0.95},
            {"url": "https://example.com/article2", "headline": "Test Article 2", "similarity_score": 0.85}
        ]
        
        # Search for articles
        query = "test query"
        results = self.pipeline.search_articles(query, limit=2)
        
        # Verify search was called with the correct parameters
        self.search_instance.search.assert_called_once_with(query, limit=2)
        
        # Check the results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["url"], "https://example.com/article1")
    
    def test_get_all_articles(self):
        """Test getting all articles."""
        # Configure mock behavior
        self.vector_store_instance.get_all_articles.return_value = [
            {"url": "https://example.com/article1", "headline": "Test Article 1"},
            {"url": "https://example.com/article2", "headline": "Test Article 2"}
        ]
        
        # Get all articles
        articles = self.pipeline.get_all_articles()
        
        # Verify get_all_articles was called
        self.vector_store_instance.get_all_articles.assert_called_once()
        
        # Check the results
        self.assertEqual(len(articles), 2)
    
    def test_clear_database(self):
        """Test clearing the database."""
        # Configure mock behavior
        self.vector_store_instance.clear.return_value = True
        
        # Clear the database
        result = self.pipeline.clear_database()
        
        # Verify clear was called
        self.vector_store_instance.clear.assert_called_once()
        
        # Check the result
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
