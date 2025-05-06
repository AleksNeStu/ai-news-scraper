"""
Unit tests for the vector_store module.
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import numpy as np

from src.vector_store import FAISSVectorStore
from src.scraper import ScrapedArticle


class TestFAISSVectorStore(unittest.TestCase):
    """Test the FAISSVectorStore implementation."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.vector_store = FAISSVectorStore(index_path=self.temp_dir)
        
        # Sample test data
        self.test_articles = [
            {
                "id": 1,
                "url": "https://example.com/article1",
                "headline": "Test Article 1",
                "text": "This is the content of test article 1",
                "source_domain": "example.com",
                "publish_date": "2023-01-01",
                "embedding": np.random.rand(1536).astype(np.float32)  # Random embedding
            },
            {
                "id": 2,
                "url": "https://example.com/article2",
                "headline": "Test Article 2",
                "text": "This is the content of test article 2",
                "source_domain": "example.com",
                "publish_date": "2023-01-02",
                "embedding": np.random.rand(1536).astype(np.float32)  # Random embedding
            }
        ]
    
    def tearDown(self):
        """Clean up after each test."""
        # Remove temporary files
        if os.path.exists(os.path.join(self.temp_dir, "faiss_index.bin")):
            os.remove(os.path.join(self.temp_dir, "faiss_index.bin"))
        if os.path.exists(os.path.join(self.temp_dir, "metadata.pkl")):
            os.remove(os.path.join(self.temp_dir, "metadata.pkl"))
        
        # Remove temporary directory
        os.rmdir(self.temp_dir)
    
    def test_store_embeddings(self):
        """Test storing embeddings in FAISS."""
        # Store embeddings
        success = self.vector_store.store_embeddings(self.test_articles)
        
        # Verify storing was successful
        self.assertTrue(success)
        
        # Verify files were created
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "faiss_index.bin")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "metadata.pkl")))
        
        # Verify the index contains the correct number of vectors
        self.assertEqual(self.vector_store.index.ntotal, len(self.test_articles))
    
    def test_search(self):
        """Test searching for similar articles."""
        # Store embeddings first
        self.vector_store.store_embeddings(self.test_articles)
        
        # Test search with the first article's embedding
        query_embedding = self.test_articles[0]["embedding"]
        results = self.vector_store.search(query_embedding, limit=2)
        
        # Verify we got results
        self.assertEqual(len(results), 2)
        
        # The first result should be the original article (highest similarity)
        self.assertEqual(results[0]["url"], self.test_articles[0]["url"])
    
    def test_get_all_articles(self):
        """Test retrieving all articles."""
        # Store embeddings first
        self.vector_store.store_embeddings(self.test_articles)
        
        # Get all articles
        articles = self.vector_store.get_all_articles()
        
        # Verify we got the correct number of articles
        self.assertEqual(len(articles), len(self.test_articles))
        
        # Verify the articles have the expected data
        self.assertEqual(articles[0]["url"], self.test_articles[0]["url"])
        self.assertEqual(articles[1]["url"], self.test_articles[1]["url"])
    
    def test_clear(self):
        """Test clearing the vector store."""
        # Store embeddings first
        self.vector_store.store_embeddings(self.test_articles)
        
        # Verify the store has data
        self.assertEqual(self.vector_store.index.ntotal, len(self.test_articles))
        
        # Clear the store
        success = self.vector_store.clear()
        
        # Verify clearing was successful
        self.assertTrue(success)
        
        # Verify the store is empty
        self.assertEqual(self.vector_store.index.ntotal, 0)
        

# Conditional mock imports for Qdrant/Pinecone tests
try:
    from src.vector_store import QdrantVectorStore, QDRANT_AVAILABLE
except ImportError:
    QDRANT_AVAILABLE = False

try:
    from src.vector_store import PineconeVectorStore, PINECONE_AVAILABLE
except ImportError:
    PINECONE_AVAILABLE = False


@unittest.skipIf(not QDRANT_AVAILABLE, "Qdrant client not available")
class TestQdrantVectorStore(unittest.TestCase):
    """Test the QdrantVectorStore implementation."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Mock the Qdrant client
        self.mock_client_patcher = patch('src.vector_store.QdrantClient')
        self.mock_client = self.mock_client_patcher.start()
        
        # Create instance with the mocked client
        self.vector_store = QdrantVectorStore(url="http://localhost:6333", collection_name="test_collection")
        
        # Sample test data
        self.test_articles = [
            {
                "id": 1,
                "url": "https://example.com/article1",
                "headline": "Test Article 1",
                "text": "This is the content of test article 1",
                "source_domain": "example.com",
                "publish_date": "2023-01-01",
                "embedding": np.random.rand(1536).astype(np.float32).tolist()
            },
            {
                "id": 2,
                "url": "https://example.com/article2",
                "headline": "Test Article 2",
                "text": "This is the content of test article 2",
                "source_domain": "example.com",
                "publish_date": "2023-01-02",
                "embedding": np.random.rand(1536).astype(np.float32).tolist()
            }
        ]
    
    def tearDown(self):
        """Clean up after each test."""
        self.mock_client_patcher.stop()
    
    def test_store_embeddings(self):
        """Test storing embeddings in Qdrant."""
        # Configure mock
        self.vector_store.client.upsert.return_value = None
        
        # Store embeddings
        success = self.vector_store.store_embeddings(self.test_articles)
        
        # Verify storing was successful
        self.assertTrue(success)
        
        # Verify client's upsert method was called
        self.vector_store.client.upsert.assert_called_once()


@unittest.skipIf(not PINECONE_AVAILABLE, "Pinecone client not available")
class TestPineconeVectorStore(unittest.TestCase):
    """Test the PineconeVectorStore implementation."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Mock Pinecone
        self.mock_pinecone_patcher = patch('src.vector_store.pinecone')
        self.mock_pinecone = self.mock_pinecone_patcher.start()
        
        # Sample API key and environment
        api_key = "test_api_key"
        environment = "test_environment"
        
        # Configure mock
        self.mock_pinecone.list_indexes.return_value = ["test_index"]
        self.mock_index = MagicMock()
        self.mock_pinecone.Index.return_value = self.mock_index
        
        # Create instance with the mocked client
        self.vector_store = PineconeVectorStore(
            api_key=api_key,
            environment=environment,
            index_name="test_index"
        )
        
        # Sample test data
        self.test_articles = [
            {
                "id": 1,
                "url": "https://example.com/article1",
                "headline": "Test Article 1",
                "text": "This is the content of test article 1",
                "source_domain": "example.com",
                "publish_date": "2023-01-01",
                "embedding": np.random.rand(1536).astype(np.float32).tolist()
            }
        ]
    
    def tearDown(self):
        """Clean up after each test."""
        self.mock_pinecone_patcher.stop()
    
    def test_store_embeddings(self):
        """Test storing embeddings in Pinecone."""
        # Configure mock
        self.mock_index.upsert.return_value = None
        
        # Store embeddings
        success = self.vector_store.store_embeddings(self.test_articles)
        
        # Verify storing was successful
        self.assertTrue(success)
        
        # Verify index's upsert method was called
        self.mock_index.upsert.assert_called_once()


if __name__ == '__main__':
    unittest.main()
