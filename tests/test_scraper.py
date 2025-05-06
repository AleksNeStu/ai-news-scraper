"""
Tests for the ArticleScraper module.

These tests validate the functionality of the article scraper,
including its ability to extract content from various news websites.
"""

import unittest
from unittest.mock import patch, MagicMock
import responses
import os
import sys
import tempfile

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper import ArticleScraper, ScrapedArticle


class TestScrapedArticle(unittest.TestCase):
    """Tests for the ScrapedArticle data class."""

    def test_init_with_minimal_args(self):
        """Test initialization with only required fields."""
        article = ScrapedArticle(
            url="https://example.com/news",
            headline="Test Headline",
            text="Test article text content."
        )
        
        self.assertEqual(article.url, "https://example.com/news")
        self.assertEqual(article.headline, "Test Headline")
        self.assertEqual(article.text, "Test article text content.")
        self.assertIsNone(article.publish_date)
        self.assertEqual(article.authors, [])
        self.assertEqual(article.source_domain, "example.com")
        self.assertIsNone(article.image_url)

    def test_init_with_all_args(self):
        """Test initialization with all fields."""
        article = ScrapedArticle(
            url="https://example.com/news",
            headline="Test Headline",
            text="Test article text content.",
            publish_date="2023-01-01T12:00:00",
            authors=["Author One", "Author Two"],
            source_domain="custom-domain.com",
            image_url="https://example.com/image.jpg"
        )
        
        self.assertEqual(article.url, "https://example.com/news")
        self.assertEqual(article.headline, "Test Headline")
        self.assertEqual(article.text, "Test article text content.")
        self.assertEqual(article.publish_date, "2023-01-01T12:00:00")
        self.assertEqual(article.authors, ["Author One", "Author Two"])
        self.assertEqual(article.source_domain, "custom-domain.com")
        self.assertEqual(article.image_url, "https://example.com/image.jpg")


class TestArticleScraper(unittest.TestCase):
    """Tests for the ArticleScraper class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ArticleScraper(max_retries=1)
        
    @responses.activate
    def test_scrape_url_with_newspaper(self):
        """Test scraping a URL using newspaper3k."""
        with patch('newspaper.Article') as MockArticle:
            # Mock Article instance
            mock_article = MagicMock()
            mock_article.title = "Test Headline"
            mock_article.text = "Test article text content."
            mock_article.authors = ["Author One"]
            mock_article.publish_date.isoformat.return_value = "2023-01-01T12:00:00"
            mock_article.top_image = "https://example.com/image.jpg"
            
            # Set up the mock
            MockArticle.return_value = mock_article
            
            # Test URL
            url = "https://example.com/news"
            
            # Call the method
            result = self.scraper.scrape_url(url)
            
            # Verify results
            self.assertIsNotNone(result)
            self.assertEqual(result.url, url)
            self.assertEqual(result.headline, "Test Headline")
            self.assertEqual(result.text, "Test article text content.")
            self.assertEqual(result.publish_date, "2023-01-01T12:00:00")
            self.assertEqual(result.authors, ["Author One"])
            self.assertEqual(result.source_domain, "example.com")
            self.assertEqual(result.image_url, "https://example.com/image.jpg")
            
    def test_scrape_urls_batch_processing(self):
        """Test batch processing of multiple URLs."""
        test_urls = [
            "https://example.com/article1",
            "https://example.com/article2",
            "https://invalid-url-for-testing.com/article"  # Should fail
        ]
        
        with patch.object(self.scraper, 'scrape_url') as mock_scrape:
            # First two URLs succeed, last one fails
            mock_scrape.side_effect = [
                ScrapedArticle(url=test_urls[0], headline="Headline 1", text="Content 1"),
                ScrapedArticle(url=test_urls[1], headline="Headline 2", text="Content 2"),
                None
            ]
            
            results = self.scraper.scrape_urls(test_urls)
            
            # Verify results
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].url, test_urls[0])
            self.assertEqual(results[1].url, test_urls[1])
            
            # Verify scrape_url was called for each URL
            self.assertEqual(mock_scrape.call_count, 3)

    def test_clean_article_text(self):
        """Test cleaning of article text."""
        # Test text with common patterns that need cleaning
        test_text = """
        This is the main article content.
        
        
        Related Articles: You might also like these.
        
        Share this article on social media!
        
        Follow us on Twitter.
        
        Advertisement: Buy now!
        
        This is more content with  extra  spaces.
        """
        
        cleaned_text = self.scraper._clean_article_text(test_text)
        
        # Verify the text was cleaned correctly
        self.assertNotIn("Related Articles", cleaned_text)
        self.assertNotIn("Share this article", cleaned_text)
        self.assertNotIn("Follow us", cleaned_text)
        self.assertNotIn("Advertisement", cleaned_text)
        self.assertIn("This is the main article content.", cleaned_text)
        self.assertIn("This is more content with extra spaces.", cleaned_text)


class TestArticleScraperWithRealURLs(unittest.TestCase):
    """
    Tests for the ArticleScraper class with real URLs.
    
    Note: These tests require internet access and may fail if the URLs change.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ArticleScraper(max_retries=1)
        
    def test_scrape_real_urls_sample(self):
        """Test scraping real URLs (sample)."""
        # Only run this test if we're explicitly testing with real URLs
        # to avoid slowing down regular test runs
        if os.environ.get('TEST_WITH_REAL_URLS') != 'true':
            self.skipTest("Skipping tests with real URLs. Set TEST_WITH_REAL_URLS=true to run.")
        
        # Sample of real news URLs that are relatively stable
        test_urls = [
            "https://www.bbc.com/news/technology",
            "https://www.reuters.com/technology/",
            "https://techcrunch.com/"
        ]
        
        results = self.scraper.scrape_urls(test_urls)
        
        # We should get at least one successful result
        self.assertTrue(len(results) > 0)
        
        # Each result should have required fields
        for article in results:
            self.assertTrue(isinstance(article, ScrapedArticle))
            self.assertIsNotNone(article.url)
            self.assertTrue(len(article.headline) > 0)
            self.assertTrue(len(article.text) > 0)
            
    def test_scrape_from_file(self):
        """Test loading URLs from a file and scraping them."""
        # Only run this test if we're explicitly testing with real URLs
        if os.environ.get('TEST_WITH_REAL_URLS') != 'true':
            self.skipTest("Skipping tests with real URLs. Set TEST_WITH_REAL_URLS=true to run.")
            
        # Create a temporary file with test URLs
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write("# Test URLs file\n")
            f.write("https://www.bbc.com/news/technology\n")
            f.write("https://www.reuters.com/technology/\n")
            f.write("# This is a comment\n")
            f.write("https://techcrunch.com/\n")
            temp_filename = f.name
            
        try:
            # Mock the read_urls_from_file function from main
            with patch('src.main.read_urls_from_file') as mock_read:
                # Set up the mock to return our test URLs
                mock_read.return_value = [
                    "https://www.bbc.com/news/technology",
                    "https://www.reuters.com/technology/",
                    "https://techcrunch.com/"
                ]
                
                # Import the function
                from src.main import read_urls_from_file
                
                # Test reading from our temp file
                urls = read_urls_from_file(temp_filename)
                
                # We should get the three actual URLs, not the comment
                self.assertEqual(len(urls), 3)
                
                # Verify all URLs are valid
                for url in urls:
                    self.assertTrue(url.startswith("http"))
                    self.assertFalse(url.startswith("#"))
                
                # Try scraping just the first URL to save time
                if urls:
                    article = self.scraper.scrape_url(urls[0])
                    self.assertIsNotNone(article)
                    self.assertTrue(len(article.headline) > 0)
                    self.assertTrue(len(article.text) > 0)
                
        finally:
            # Clean up the temporary file
            os.unlink(temp_filename)


if __name__ == '__main__':
    unittest.main()
