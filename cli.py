#!/usr/bin/env python3
"""
Command-line utility for AI News Scraper.

This script provides a simple command-line interface to demonstrate
the capabilities of the AI News Scraper package.

Example usage:
  python cli.py process --urls https://example.com/article
  python cli.py search "artificial intelligence"
  python cli.py list
  python cli.py clear
"""

import argparse
import json
import sys
import logging

from src.config import validate_config, suppress_external_library_warnings
from src.main import NewsScraperPipeline

# Suppress warnings from external libraries
suppress_external_library_warnings()


def setup_logging():
    """Configure logging for the command-line interface."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def process_command(args):
    """
    Process URLs command handler.
    
    Args:
        args: Command-line arguments.
    """
    # Get URLs from file or direct input
    urls = []
    if args.urls:
        urls = args.urls
    elif args.file:
        from src.main import read_urls_from_file
        urls = read_urls_from_file(args.file)
        
    if not urls:
        print("\nError: No URLs to process. Please provide URLs or a valid file.")
        return
    
    pipeline = NewsScraperPipeline(use_enhanced=args.enhanced)
    results = pipeline.process_urls(urls)
    
    # Print results
    print("\n=== Processing Results ===")
    print(f"Processed {results['processed_count']} of {results['total_urls']} URLs")
    print(f"Time taken: {results['elapsed_seconds']:.2f} seconds")
    print(f"Success: {results['success']}")


def search_command(args):
    """
    Search command handler.
    
    Args:
        args: Command-line arguments.
    """
    pipeline = NewsScraperPipeline()
    results = pipeline.search_articles(args.query, limit=args.limit)
    
    # Print results
    print(f"\n=== Search Results for '{args.query}' ===")
    if not results:
        print("No results found.")
    
    for i, result in enumerate(results, 1):
        print(f"\n--- Result #{i} (Score: {result['similarity_score']:.4f}) ---")
        print(f"Title: {result['headline']}")
        print(f"Source: {result['source_domain']}")
        if 'publish_date' in result and result['publish_date']:
            print(f"Date: {result['publish_date']}")
        print(f"URL: {result['url']}")
        if 'summary' in result and result['summary']:
            print(f"\nSummary: {result['summary']}")
        print("-" * 60)


def list_command(args):
    """
    List command handler.
    
    Args:
        args: Command-line arguments.
    """
    pipeline = NewsScraperPipeline()
    articles = pipeline.get_all_articles()
    
    # Print results
    print(f"\n=== All Articles ({len(articles)}) ===")
    if not articles:
        print("No articles found in the database.")
    
    for i, article in enumerate(articles, 1):
        print(f"\n{i}. {article['headline']}")
        print(f"   Source: {article['source_domain']}")
        if 'publish_date' in article and article['publish_date']:
            print(f"   Date: {article['publish_date']}")
        print(f"   URL: {article['url']}")


def clear_command(args):
    """
    Clear command handler.
    
    Args:
        args: Command-line arguments.
    """
    pipeline = NewsScraperPipeline()
    
    if args.force:
        success = pipeline.clear_database()
        print(f"Database cleared: {success}")
    else:
        confirm = input("Are you sure you want to clear the database? This cannot be undone. (y/N): ")
        if confirm.lower() == 'y':
            success = pipeline.clear_database()
            print(f"Database cleared: {success}")
        else:
            print("Operation cancelled.")


def main():
    """Main entry point for the command-line interface."""
    setup_logging()
    
    # Validate configuration
    if not validate_config():
        print("Error: Invalid configuration. Please check your .env file.")
        sys.exit(1)
    
    # Create parser
    parser = argparse.ArgumentParser(
        description="AI News Scraper and Semantic Search"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Process URLs command
    process_parser = subparsers.add_parser("process", help="Process URLs")
    url_group = process_parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument("--urls", nargs="+", help="URLs to process (space-separated)")
    url_group.add_argument("--file", type=str, help="Path to file containing URLs (one per line)")
    process_parser.add_argument("--enhanced", action="store_true", help="Use enhanced processing")
    process_parser.set_defaults(func=process_command)
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search articles")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=5, help="Maximum number of results")
    search_parser.set_defaults(func=search_command)
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all articles")
    list_parser.set_defaults(func=list_command)
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear the vector database")
    clear_parser.add_argument("--force", action="store_true", help="Skip confirmation")
    clear_parser.set_defaults(func=clear_command)
    
    # Parse arguments
    args = parser.parse_args()
    
    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
