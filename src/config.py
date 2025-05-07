"""
Configuration and environment setup for the AI News Scraper application.
"""
import os
import warnings
import importlib.util
from typing import Optional, Literal, Union
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Suppress specific deprecation warnings from libraries
def suppress_external_library_warnings():
    """
    Suppress specific deprecation warnings from external libraries 
    like FAISS, SWIG, etc.
    """
    # Suppress numpy core deprecation warnings used by FAISS
    warnings.filterwarnings(
        "ignore", 
        message="numpy.core._multiarray_umath is deprecated", 
        category=DeprecationWarning
    )
    
    # Suppress SWIG-related warnings about missing __module__ attribute
    warnings.filterwarnings(
        "ignore",
        message="builtin type .* has no __module__ attribute",
        category=DeprecationWarning
    )

# Call this function to suppress warnings
suppress_external_library_warnings()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
COMPLETION_MODEL = os.getenv("COMPLETION_MODEL", "gpt-3.5-turbo")
SUMMARY_MAX_TOKENS = int(os.getenv("SUMMARY_MAX_TOKENS", 300))
SUMMARY_MIN_TOKENS = int(os.getenv("SUMMARY_MIN_TOKENS", 100))

# Offline mode configuration
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "False").lower() in ["true", "1", "yes"]
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

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


@dataclass
class Config:
    """Configuration class for AI News Scraper application."""
    
    # OpenAI API settings
    openai_api_key: str = OPENAI_API_KEY
    embedding_model: str = EMBEDDING_MODEL
    completion_model: str = COMPLETION_MODEL
    summary_max_tokens: int = SUMMARY_MAX_TOKENS
    summary_min_tokens: int = SUMMARY_MIN_TOKENS
    
    # Offline mode settings
    offline_mode: bool = OFFLINE_MODE
    local_embedding_model: str = LOCAL_EMBEDDING_MODEL
    
    # Vector database settings
    vector_db_type: str = VECTOR_DB_TYPE.lower()
    vector_db_path: str = FAISS_INDEX_PATH
    
    # Application settings
    max_retry_attempts: int = MAX_RETRY_ATTEMPTS
    log_level: str = LOG_LEVEL
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        # Create directory for vector store if it doesn't exist (for FAISS)
        if self.vector_db_type.upper() == "FAISS":
            os.makedirs(os.path.dirname(self.vector_db_path), exist_ok=True)
    
    def to_dict(self) -> dict:
        """Convert configuration to a dictionary."""
        return {
            "openai_api_key": "***" if self.openai_api_key else None,  # Mask API key
            "embedding_model": self.embedding_model,
            "completion_model": self.completion_model,
            "summary_max_tokens": self.summary_max_tokens,
            "summary_min_tokens": self.summary_min_tokens,
            "offline_mode": self.offline_mode,
            "local_embedding_model": self.local_embedding_model,
            "vector_db_type": self.vector_db_type,
            "vector_db_path": self.vector_db_path,
            "max_retry_attempts": self.max_retry_attempts,
            "log_level": self.log_level
        }
    
    def validate(self) -> bool:
        """
        Validate the configuration.
        
        Returns:
            bool: True if configuration is valid, False otherwise.
        """
        # Skip API key validation in offline mode
        if not self.offline_mode and not self.openai_api_key:
            print("Error: OpenAI API key is not set and offline_mode is False")
            return False
        
        # Check vector database configuration
        if self.vector_db_type.upper() not in ["FAISS", "QDRANT", "PINECONE"]:
            print(f"Error: Unknown vector database type: {self.vector_db_type}")
            return False
        
        return True
