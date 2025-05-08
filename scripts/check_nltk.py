#!/usr/bin/env python
"""
Script to verify NLTK resources required by AI News Scraper.

This script checks that all the required NLTK resources are installed
and properly available, and can download any missing resources.

Usage:
    python scripts/check_nltk.py [--download]

Options:
    --download    Automatically download any missing resources
"""

import os
import sys
import argparse
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("nltk-check")

def check_nltk_resources(download=False):
    """Check if required NLTK resources are available and optionally download them."""
    try:
        import nltk
        
        # Create project-specific NLTK data directory if it doesn't exist
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        nltk_data_dir = os.path.join(project_root, "nltk_data")
        os.makedirs(nltk_data_dir, exist_ok=True)
        
        # Add this directory to NLTK's search path
        nltk.data.path.append(nltk_data_dir)
        logger.info(f"NLTK search paths: {nltk.data.path}")
        
        # Resources required by the application
        resources = {
            "punkt": "tokenizers/punkt",
            "stopwords": "corpora/stopwords",
            "averaged_perceptron_tagger": "taggers/averaged_perceptron_tagger",
            "punkt_tab": "tokenizers/punkt_tab"
        }
        
        all_available = True
        for resource_name, resource_path in resources.items():
            try:
                nltk.data.find(resource_path)
                logger.info(f"✅ Resource '{resource_name}' is available")
            except LookupError:
                all_available = False
                if download:
                    logger.info(f"Downloading NLTK resource '{resource_name}'...")
                    nltk.download(resource_name, download_dir=nltk_data_dir)
                    try:
                        nltk.data.find(resource_path)
                        logger.info(f"✅ Resource '{resource_name}' has been downloaded")
                    except LookupError:
                        logger.error(f"❌ Failed to download '{resource_name}'")
                        return False
                else:
                    logger.warning(f"❌ Resource '{resource_name}' is missing. Use --download option to install.")
        
        return all_available
    except ImportError:
        logger.error("NLTK is not installed. Please install it with: pip install nltk")
        return False
    except Exception as e:
        logger.error(f"An error occurred while checking NLTK resources: {str(e)}")
        return False

def main():
    print("Starting NLTK resource check...")
    parser = argparse.ArgumentParser(description="Check and optionally download required NLTK resources")
    parser.add_argument("--download", action="store_true", help="Download missing resources")
    args = parser.parse_args()
    
    print("Checking NLTK resources...")
    logger.info("Checking NLTK resources...")
    result = check_nltk_resources(args.download)
    
    if result:
        logger.info("All required NLTK resources are available")
        sys.exit(0)
    elif not args.download:
        logger.info("Some resources are missing. Run with --download to install them")
        sys.exit(1)
    else:
        logger.error("Failed to download all required resources")
        sys.exit(2)

if __name__ == "__main__":
    main()
