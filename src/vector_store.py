"""
Vector Store module for handling vector database operations.

This module provides functionality to store, retrieve, and manage article embeddings
in various vector databases (FAISS, Qdrant, Pinecone) for semantic search.
"""

import logging
import os
import json
from typing import Dict, List, Optional, Any, Union
from abc import ABC, abstractmethod
import pickle

import numpy as np
import faiss
from tqdm import tqdm

# Import conditionally to avoid dependency errors
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

try:
    import pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False

from src.config import (
    VECTOR_DB_TYPE, FAISS_INDEX_PATH, 
    QDRANT_URL, QDRANT_COLLECTION_NAME,
    PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX_NAME
)

# Configure logging
logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Abstract base class for vector database implementations."""
    
    @abstractmethod
    def store_embeddings(self, embedded_articles: List[Dict[str, Any]]) -> bool:
        """
        Store article embeddings in the vector database.
        
        Args:
            embedded_articles: List of articles with their embeddings.
            
        Returns:
            bool: True if storing was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def search(self, query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar articles in the vector database.
        
        Args:
            query_embedding: Embedding vector of the query.
            limit: Maximum number of results to return.
            
        Returns:
            List[Dict[str, Any]]: List of similar articles with similarity scores.
        """
        pass

    @abstractmethod
    def get_all_articles(self) -> List[Dict[str, Any]]:
        """
        Retrieve all stored articles.
        
        Returns:
            List[Dict[str, Any]]: List of all stored articles with their embeddings and metadata.
        """
        pass
    
    @abstractmethod
    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """
        Retrieve metadata for all stored articles without embeddings.
        
        Returns:
            List[Dict[str, Any]]: List of all stored article metadata.
        """
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """
        Clear all data from the vector store.
        
        Returns:
            bool: True if clearing was successful, False otherwise.
        """
        pass


class FAISSVectorStore(VectorStore):
    """FAISS implementation of the vector store."""
    
    def __init__(self, index_path: str = FAISS_INDEX_PATH):
        """
        Initialize the FAISS vector store.
        
        Args:
            index_path: Path to store the FAISS index and metadata.
        """
        self.index_path = index_path
        self.index_file = os.path.join(index_path, "faiss_index.bin")
        self.metadata_file = os.path.join(index_path, "metadata.pkl")
        
        # Create directory if it doesn't exist
        os.makedirs(index_path, exist_ok=True)
        
        # Initialize or load index and metadata
        self._initialize()
    
    def _initialize(self):
        """Initialize or load the FAISS index and metadata."""
        if os.path.exists(self.index_file) and os.path.exists(self.metadata_file):
            try:
                # Load existing index
                self.index = faiss.read_index(self.index_file)
                
                # Load metadata
                with open(self.metadata_file, 'rb') as f:
                    self.metadata = pickle.load(f)
                
                logger.info(f"Loaded existing FAISS index with {self.index.ntotal} vectors")
            except Exception as e:
                logger.error(f"Error loading FAISS index: {str(e)}")
                self._create_new_index()
        else:
            self._create_new_index()
    
    def _create_new_index(self):
        """Create a new FAISS index."""
        # Initialize empty metadata dictionary
        self.metadata = {}
        
        # Create a new index with 1536 dimensions (OpenAI's default)
        self.index = faiss.IndexFlatL2(1536)
        logger.info("Created new FAISS index")
    
    def store_embeddings(self, embedded_articles: List[Dict[str, Any]]) -> bool:
        """
        Store article embeddings in FAISS.
        
        Args:
            embedded_articles: List of dictionaries containing article embeddings and metadata.
            
        Returns:
            bool: True if storage was successful, False otherwise.
        """
        try:
            if not embedded_articles:
                logger.warning("No embeddings to store")
                return False
                
            # Extract embeddings and metadata
            embeddings = []
            for idx, article in enumerate(embedded_articles):
                # Get the embedding vector
                embedding = article["embedding"]
                if not isinstance(embedding, np.ndarray):
                    embedding = np.array(embedding, dtype=np.float32)
                
                # Store the embedding
                embeddings.append(embedding)
                
                # Store metadata without the embedding vectors to save space
                metadata_copy = {k: v for k, v in article.items() 
                                if k not in ["embedding", "title_embedding", "summary_embedding"]}
                
                # Store the id and index in the metadata
                article_id = article.get("id", len(self.metadata) + idx)
                self.metadata[article_id] = metadata_copy
            
            # Convert embeddings to numpy array
            embeddings_array = np.array(embeddings, dtype=np.float32)
            
            # Add embeddings to the index
            self.index.add(embeddings_array)
            
            # Save the index and metadata
            faiss.write_index(self.index, self.index_file)
            with open(self.metadata_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            
            logger.info(f"Stored {len(embedded_articles)} embeddings in FAISS")
            return True
            
        except Exception as e:
            logger.error(f"Error storing embeddings in FAISS: {str(e)}")
            return False
    
    def search(self, query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for articles similar to the query embedding.
        
        Args:
            query_embedding: Vector embedding of the search query.
            limit: Maximum number of results to return.
            
        Returns:
            List[Dict[str, Any]]: List of similar articles with similarity scores.
        """
        try:
            # Check if index is empty
            if self.index.ntotal == 0:
                logger.warning("Cannot search, FAISS index is empty")
                return []
                
            # Convert query to numpy array
            if not isinstance(query_embedding, np.ndarray):
                query_embedding = np.array([query_embedding], dtype=np.float32)
            else:
                query_embedding = query_embedding.reshape(1, -1).astype('float32')
            
            # Search the index
            limit = min(limit, self.index.ntotal)  # Don't request more results than vectors
            distances, indices = self.index.search(query_embedding, limit)
            
            results = []
            for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                # Convert distance to similarity score (1 / (1 + distance))
                similarity = 1 / (1 + dist)
                
                # Find the article ID in the metadata
                article_ids = list(self.metadata.keys())
                if idx < len(article_ids):
                    article_id = article_ids[idx]
                    article_data = self.metadata.get(article_id, {})
                    
                    # Add similarity score
                    result = {
                        "id": article_id,
                        "similarity": float(similarity),  # Convert numpy float to Python float
                        **article_data
                    }
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching FAISS index: {str(e)}")
            return []

    def get_all_articles(self) -> List[Dict[str, Any]]:
        """
        Retrieve all stored articles.
        
        Returns:
            List[Dict[str, Any]]: List of all stored articles with their metadata.
        """
        try:
            return [{"id": k, **v} for k, v in self.metadata.items()]
        except Exception as e:
            logger.error(f"Error retrieving articles from FAISS: {str(e)}")
            return []
            
    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """
        Retrieve metadata for all stored articles without embeddings.
        
        Returns:
            List[Dict[str, Any]]: List of all stored article metadata.
        """
        try:
            # Return metadata without the embedding fields
            articles = []
            for article_id, metadata in self.metadata.items():
                # Copy metadata without embedding fields
                clean_metadata = {k: v for k, v in metadata.items() 
                               if k not in ["embedding", "title_embedding", "summary_embedding"]}
                articles.append({"id": article_id, **clean_metadata})
            return articles
        except Exception as e:
            logger.error(f"Error retrieving metadata from FAISS: {str(e)}")
            return []
    
    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """
        Retrieve metadata for all stored articles without embeddings.
        
        Returns:
            List[Dict[str, Any]]: List of all stored article metadata.
        """
        try:
            # Return metadata directly
            return [v for v in self.metadata.values()]
        except Exception as e:
            logger.error(f"Error retrieving metadata from FAISS: {str(e)}")
            return []
    
    def clear(self) -> bool:
        """
        Clear all data from the FAISS store.
        
        Returns:
            bool: True if clearing was successful, False otherwise.
        """
        try:
            # Create a new index
            self._create_new_index()
            
            # Save the empty index and metadata
            faiss.write_index(self.index, self.index_file)
            with open(self.metadata_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            
            logger.info("Cleared FAISS index")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing FAISS index: {str(e)}")
            return False

    def store_articles_without_embeddings(self, articles: List[Dict[str, Any]]) -> bool:
        """
        Store articles in the database without embeddings (fallback method).
        
        Args:
            articles: List of article dictionaries.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # For FAISS, we can use random vectors as placeholders
            if not articles:
                logger.warning("No articles to store")
                return False
                
            # Generate random embeddings as placeholders
            import numpy as np
            dimension = 1536  # Default for OpenAI embeddings
            
            for article in articles:
                # Create a random embedding vector (normalized)
                random_embedding = np.random.rand(dimension).astype(np.float32)
                random_embedding = random_embedding / np.linalg.norm(random_embedding)
                
                # Add the random embedding to the article
                article["embedding"] = random_embedding
                    
            # Now use the regular store method
            return self.store_embeddings(articles)
                
        except Exception as e:
            logger.error(f"Error storing articles without embeddings: {str(e)}")
            return False


class QdrantVectorStore(VectorStore):
    """Qdrant implementation of the vector store."""
    
    def __init__(self, url: str = QDRANT_URL, collection_name: str = QDRANT_COLLECTION_NAME):
        """
        Initialize the Qdrant vector store.
        
        Args:
            url: URL of the Qdrant server.
            collection_name: Name of the collection to use.
        """
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant client is not installed. Please install it with 'pip install qdrant-client'")
            
        self.url = url
        self.collection_name = collection_name
        
        # Initialize client
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Qdrant client and create collection if it doesn't exist."""
        try:
            self.client = QdrantClient(url=self.url)
            
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [collection.name for collection in collections]
            
            if self.collection_name not in collection_names:
                # Create new collection (1536 dimensions for OpenAI embeddings)
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=1536,
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"Created new Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"Connected to existing Qdrant collection: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Error initializing Qdrant client: {str(e)}")
            raise
    
    def store_embeddings(self, embedded_articles: List[Dict[str, Any]]) -> bool:
        """
        Store article embeddings in Qdrant.
        
        Args:
            embedded_articles: List of dictionaries containing article embeddings and metadata.
            
        Returns:
            bool: True if storage was successful, False otherwise.
        """
        try:
            if not embedded_articles:
                logger.warning("No embeddings to store")
                return False
                
            points = []
            for article in embedded_articles:
                # Extract and convert embedding to list if it's numpy array
                embedding = article["embedding"]
                if isinstance(embedding, np.ndarray):
                    embedding = embedding.tolist()
                
                # Extract id or create one
                article_id = article.get("id", hash(article["url"]))
                
                # Create payload (metadata without embeddings)
                payload = {k: v for k, v in article.items() 
                          if k not in ["embedding", "id", "title_embedding", "summary_embedding"]}
                
                # Add point
                points.append(
                    models.PointStruct(
                        id=article_id,
                        vector=embedding,
                        payload=payload
                    )
                )
            
            # Upload in batches to avoid request size limitations
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch
                )
            
            logger.info(f"Stored {len(embedded_articles)} embeddings in Qdrant")
            return True
            
        except Exception as e:
            logger.error(f"Error storing embeddings in Qdrant: {str(e)}")
            return False
    
    def search(self, query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for articles similar to the query embedding.
        
        Args:
            query_embedding: Vector embedding of the search query.
            limit: Maximum number of results to return.
            
        Returns:
            List[Dict[str, Any]]: List of similar articles with similarity scores.
        """
        try:
            # Convert numpy array to list if needed
            if isinstance(query_embedding, np.ndarray):
                query_embedding = query_embedding.tolist()
            
            # Search in Qdrant
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit
            )
            
            results = []
            for scored_point in search_result:
                result = {
                    "id": scored_point.id,
                    "similarity": scored_point.score,
                    **scored_point.payload
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Qdrant: {str(e)}")
            return []

    def get_all_articles(self) -> List[Dict[str, Any]]:
        """
        Retrieve all stored articles.
        
        Returns:
            List[Dict[str, Any]]: List of all stored articles with their metadata.
        """
        try:
            # Get all points from the collection
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                limit=10000  # Use a large limit, may need pagination for very large collections
            )
            
            results = []
            for point in scroll_result[0]:
                result = {
                    "id": point.id,
                    **point.payload
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving articles from Qdrant: {str(e)}")
            return []
    
    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """
        Retrieve metadata for all stored articles without embeddings.
        
        Returns:
            List[Dict[str, Any]]: List of all stored article metadata.
        """
        try:
            # For Qdrant, metadata is stored in the payload of each point
            # We need to scroll through all points to collect metadata
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                limit=10000  # Use a large limit, may need pagination for very large collections
            )
            
            results = []
            for point in scroll_result[0]:
                metadata = {
                    "id": point.id,
                    **point.payload
                }
                results.append(metadata)
            
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving metadata from Qdrant: {str(e)}")
            return []
    
    def clear(self) -> bool:
        """
        Clear all data from the Qdrant store.
        
        Returns:
            bool: True if clearing was successful, False otherwise.
        """
        try:
            # Delete the collection
            self.client.delete_collection(collection_name=self.collection_name)
            
            # Recreate the collection
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=1536,
                    distance=models.Distance.COSINE
                )
            )
            
            logger.info("Cleared Qdrant collection")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing Qdrant collection: {str(e)}")
            return False

    def store_articles_without_embeddings(self, articles: List[Dict[str, Any]]) -> bool:
        """
        Store articles in Qdrant without embeddings (fallback method).
        
        Args:
            articles: List of article dictionaries.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # For Qdrant, we'll use random vectors as placeholders
            if not articles:
                logger.warning("No articles to store")
                return False
                
            # Generate random embeddings as placeholders
            import numpy as np
            dimension = 1536  # Default for OpenAI embeddings
            
            for article in articles:
                # Create a random embedding vector (normalized)
                random_embedding = np.random.rand(dimension).astype(np.float32)
                random_embedding = random_embedding / np.linalg.norm(random_embedding)
                
                # Add the random embedding to the article
                article["embedding"] = random_embedding
                    
            # Now use the regular store method
            return self.store_embeddings(articles)
                
        except Exception as e:
            logger.error(f"Error storing articles without embeddings in Qdrant: {str(e)}")
            return False


class PineconeVectorStore(VectorStore):
    """Pinecone implementation of the vector store."""
    
    def __init__(self, api_key: str = PINECONE_API_KEY, 
                 environment: str = PINECONE_ENVIRONMENT,
                 index_name: str = PINECONE_INDEX_NAME):
        """
        Initialize the Pinecone vector store.
        
        Args:
            api_key: Pinecone API key.
            environment: Pinecone environment.
            index_name: Name of the Pinecone index to use.
        """
        if not PINECONE_AVAILABLE:
            raise ImportError("Pinecone is not installed. Please install it with 'pip install pinecone-client'")
        
        if not api_key:
            raise ValueError("Pinecone API key is required")
            
        self.api_key = api_key
        self.environment = environment
        self.index_name = index_name
        
        # Initialize Pinecone client and index
        self._initialize()
    
    def _initialize(self):
        """Initialize the Pinecone client and index."""
        try:
            # Initialize Pinecone
            pinecone.init(api_key=self.api_key, environment=self.environment)
            
            # Check if index exists
            if self.index_name not in pinecone.list_indexes():
                # Create the index
                pinecone.create_index(
                    name=self.index_name,
                    dimension=1536,  # OpenAI embedding dimension
                    metric="cosine"
                )
                logger.info(f"Created new Pinecone index: {self.index_name}")
            
            # Connect to the index
            self.index = pinecone.Index(self.index_name)
            logger.info(f"Connected to Pinecone index: {self.index_name}")
            
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {str(e)}")
            raise
    
    def store_embeddings(self, embedded_articles: List[Dict[str, Any]]) -> bool:
        """
        Store article embeddings in Pinecone.
        
        Args:
            embedded_articles: List of dictionaries containing article embeddings and metadata.
            
        Returns:
            bool: True if storage was successful, False otherwise.
        """
        try:
            if not embedded_articles:
                logger.warning("No embeddings to store")
                return False
                
            vectors = []
            for article in embedded_articles:
                # Extract embedding
                embedding = article["embedding"]
                if isinstance(embedding, np.ndarray):
                    embedding = embedding.tolist()
                
                # Extract id or create one
                article_id = str(article.get("id", hash(article["url"])))
                
                # Create metadata (without embeddings)
                metadata = {k: v for k, v in article.items() 
                           if k not in ["embedding", "id", "title_embedding", "summary_embedding"]}
                
                # Add vector
                vectors.append((article_id, embedding, metadata))
            
            # Upload in batches to avoid request size limitations
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                self.index.upsert(vectors=batch)
            
            logger.info(f"Stored {len(embedded_articles)} embeddings in Pinecone")
            return True
            
        except Exception as e:
            logger.error(f"Error storing embeddings in Pinecone: {str(e)}")
            return False
    
    def search(self, query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for articles similar to the query embedding.
        
        Args:
            query_embedding: Vector embedding of the search query.
            limit: Maximum number of results to return.
            
        Returns:
            List[Dict[str, Any]]: List of similar articles with similarity scores.
        """
        try:
            # Convert numpy array to list if needed
            if isinstance(query_embedding, np.ndarray):
                query_embedding = query_embedding.tolist()
            
            # Query the index
            query_result = self.index.query(
                vector=query_embedding,
                top_k=limit,
                include_metadata=True
            )
            
            results = []
            for match in query_result.matches:
                result = {
                    "id": match.id,
                    "similarity": match.score,
                    **match.metadata
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Pinecone: {str(e)}")
            return []

    def get_all_articles(self) -> List[Dict[str, Any]]:
        """
        Retrieve all stored articles.
        
        Returns:
            List[Dict[str, Any]]: List of all stored articles with their metadata.
        """
        try:
            # Note: Pinecone doesn't have a direct "get all" function
            # We would need to fetch all IDs first, then retrieve their data
            logger.warning("Getting all articles from Pinecone is not directly supported")
            return []
            
        except Exception as e:
            logger.error(f"Error retrieving articles from Pinecone: {str(e)}")
            return []
    
    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """
        Retrieve metadata for all stored articles without embeddings.
        
        Returns:
            List[Dict[str, Any]]: List of all stored article metadata.
        """
        try:
            # For Pinecone, we can only retrieve metadata for specific IDs
            # We need to maintain a separate list of all IDs (not efficient, but works)
            all_ids = self.index.describe_index_stats().vector_count
            logger.info(f"Total vectors in Pinecone index: {all_ids}")
            
            # Fetch metadata for all IDs
            metadata = []
            for id in all_ids:
                try:
                    result = self.index.fetch(ids=[id])
                    if result and result.vectors:
                        metadata.append(result.vectors[0].metadata)
                except Exception as e:
                    logger.warning(f"Error fetching metadata for id {id}: {str(e)}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error retrieving metadata from Pinecone: {str(e)}")
            return []
    
    def clear(self) -> bool:
        """
        Clear all data from the Pinecone store.
        
        Returns:
            bool: True if clearing was successful, False otherwise.
        """
        try:
            # Delete all vectors (but keep the index)
            self.index.delete(delete_all=True)
            
            logger.info("Cleared Pinecone index")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing Pinecone index: {str(e)}")
            return False

    def store_articles_without_embeddings(self, articles: List[Dict[str, Any]]) -> bool:
        """
        Store articles in Pinecone without embeddings (fallback method).
        
        Args:
            articles: List of article dictionaries.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # For Pinecone, we'll use random vectors as placeholders
            if not articles:
                logger.warning("No articles to store")
                return False
                
            # Generate random embeddings as placeholders
            import numpy as np
            dimension = 1536  # Default for OpenAI embeddings
            
            for article in articles:
                # Create a random embedding vector (normalized)
                random_embedding = np.random.rand(dimension).astype(np.float32)
                random_embedding = random_embedding / np.linalg.norm(random_embedding)
                
                # Add the random embedding to the article
                article["embedding"] = random_embedding
                    
            # Now use the regular store method
            return self.store_embeddings(articles)
                
        except Exception as e:
            logger.error(f"Error storing articles without embeddings in Pinecone: {str(e)}")
            return False


def get_vector_store() -> VectorStore:
    """
    Factory function to get the configured vector store instance.
    
    Returns:
        VectorStore: An instance of the configured vector store.
    """
    if VECTOR_DB_TYPE == "FAISS":
        return FAISSVectorStore(index_path=FAISS_INDEX_PATH)
    elif VECTOR_DB_TYPE == "QDRANT":
        return QdrantVectorStore(url=QDRANT_URL, collection_name=QDRANT_COLLECTION_NAME)
    elif VECTOR_DB_TYPE == "PINECONE":
        return PineconeVectorStore(
            api_key=PINECONE_API_KEY,
            environment=PINECONE_ENVIRONMENT,
            index_name=PINECONE_INDEX_NAME
        )
    else:
        logger.error(f"Unknown vector database type: {VECTOR_DB_TYPE}")
        # Default to FAISS
        return FAISSVectorStore(index_path=FAISS_INDEX_PATH)
