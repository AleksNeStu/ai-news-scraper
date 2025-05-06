"""
Configuration and environment setup for the AI News Scraper application.
"""
import os
from typing import Optional, Literal
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
COMPLETION_MODEL = os.getenv("COMPLETION_MODEL", "gpt-3.5-turbo")
SUMMARY_MAX_TOKENS = int(os.getenv("SUMMARY_MAX_TOKENS", 300))
SUMMARY_MIN_TOKENS = int(os.getenv("SUMMARY_MIN_TOKENS", 100))

# Vector Database Configuration
VECTOR_DB_TYPE: Literal["FAISS", "QDRANT", "PINECONE"] = os.getenv("VECTOR_DB_TYPE", "FAISS")

# FAISS specific configuration
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "./data/vector_index")

# Qdrant specific configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "news_articles")

# Pinecone specific configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "news_articles")

# Application Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", 3))

def validate_config() -> bool:
    """
    Validates that all required configuration is present.
    
    Returns:
        bool: True if configuration is valid, False otherwise.
    """
    # Check for required OpenAI configuration
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY is not set in .env file")
        return False
        
    # Check vector database configuration
    if VECTOR_DB_TYPE == "FAISS":
        # Create directory for FAISS index if it doesn't exist
        os.makedirs(os.path.dirname(FAISS_INDEX_PATH), exist_ok=True)
    elif VECTOR_DB_TYPE == "QDRANT":
        # No specific validation required for Qdrant
        pass
    elif VECTOR_DB_TYPE == "PINECONE":
        if not PINECONE_API_KEY:
            print("Error: PINECONE_API_KEY is not set in .env file")
            return False
        if not PINECONE_ENVIRONMENT:
            print("Error: PINECONE_ENVIRONMENT is not set in .env file")
            return False
    else:
        print(f"Error: Unknown VECTOR_DB_TYPE: {VECTOR_DB_TYPE}")
        return False
        
    return True
