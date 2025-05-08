"""
Test NLTK resources functionality.
"""
import os
import pytest
from unittest import mock
from src.search import download_nltk_resources, SemanticSearchEngine


def test_download_nltk_resources():
    """Test that NLTK resources are downloaded correctly."""
    # Mock nltk.data.find to simulate resources not found
    with mock.patch('nltk.data.find', side_effect=LookupError('Resource not found')):
        with mock.patch('nltk.download', return_value=True) as mock_download:
            # Call the function
            download_nltk_resources()
            
            # Check that download was called for each expected resource
            expected_resources = ["punkt", "stopwords", "averaged_perceptron_tagger", "punkt_tab"]
            actual_resources = [args[0] for args, _ in mock_download.call_args_list]
            
            # Verify that all expected resources were downloaded
            for resource in expected_resources:
                assert resource in actual_resources, f"Resource {resource} was not downloaded"


def test_text_search_initialization():
    """Test text search initialization."""
    with mock.patch('src.vector_store.get_vector_store'):
        # Create a search engine instance
        search_engine = SemanticSearchEngine()
        
        # Verify that tokenize and stopwords are set properly
        assert search_engine.tokenize is not None
        assert search_engine.stopwords is not None
        assert len(search_engine.stopwords) > 0
