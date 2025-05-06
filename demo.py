#!/usr/bin/env python3
"""
Demo script for AI News Scraper.

This script demonstrates the complete workflow of the AI News Scraper application:
1. Scraping articles from specified URLs
2. Summarizing articles and extracting topics
3. Storing embeddings in a vector database
4. Performing semantic searches

Usage:
    poetry run python demo.py
"""

import os
import time
from typing import List
from dotenv import load_dotenv

from src.main import NewsPipeline
from src.config import validate_config

# Sample URLs for demonstration
DEMO_URLS = [
    # Technology news
    "https://www.bbc.com/news/technology-68064311",  # BBC - AI news
    "https://www.theverge.com/2023/2/7/23587454/microsoft-bing-edge-chatgpt-ai",  # The Verge - AI article
    "https://techcrunch.com/2023/02/13/openai-releases-tool-to-detect-ai-generated-text/",  # TechCrunch - AI detection
    
    # Business & Science news
    "https://www.reuters.com/technology/openai-agrees-buy-windsurf-about-3-billion-bloomberg-news-reports-2023-04-06/",  # Reuters - OpenAI acquisition
    "https://www.cnbc.com/2023/02/14/tesla-recalls-362758-vehicles-says-full-self-driving-beta-may-cause-crashes.html",  # CNBC - Tesla
    "https://www.scientificamerican.com/article/james-webb-space-telescope-spots-ancient-galaxies-that-shouldnt-exist/",  # Space
]

DEMO_SEARCH_QUERIES = [
    "AI ethical concerns",
    "How is ChatGPT being used?",
    "Privacy implications of AI",
    "Latest developments in generative AI",
    "AI regulation and policy",
    "AI in healthcare applications",
]


def color_print(text: str, color: str = "blue"):
    """Print colored text to the console."""
    colors = {
        "blue": "\033[94m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "end": "\033[0m",
        "bold": "\033[1m",
    }
    print(f"{colors.get(color, '')}{text}{colors['end']}")


def section_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    color_print(f" {title} ".center(80, "="), "bold")
    print("=" * 80)


def check_environment():
    """Check that the environment is properly configured."""
    section_header("Environment Check")
    
    # Check if .env file exists
    if not os.path.exists(".env"):
        color_print("Warning: .env file not found!", "yellow")
        color_print("Creating a temporary .env file for demo purposes...", "yellow")
        with open(".env", "w") as f:
            f.write("# Temporary .env file for demo\n")
            f.write("OPENAI_API_KEY=your-openai-api-key-here\n")
            f.write("VECTOR_DB_TYPE=FAISS\n")
            f.write("FAISS_INDEX_PATH=./data/vector_index\n")
    
    # Check for OpenAI API key
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-openai-api-key-here":
        color_print("Error: OpenAI API key not configured!", "red")
        color_print("Please set your OpenAI API key in the .env file", "red")
        color_print("Example: OPENAI_API_KEY=sk-...", "yellow")
        return False
    
    # Validate configuration
    if not validate_config():
        color_print("Error: Invalid configuration!", "red")
        return False
    
    color_print("Environment check passed!", "green")
    return True


def demo_scraping(pipeline: NewsPipeline):
    """Demonstrate article scraping."""
    section_header("Article Scraping")
    
    # Demonstrate both direct URL processing and file-based URL processing
    color_print("Demonstration has two parts:", "bold")
    color_print("1. Direct URL processing", "blue")
    color_print("2. File-based URL processing (using urls.txt)", "blue")
    
    # Part 1: Direct URL processing
    color_print("\nPart 1: Direct URL Processing", "bold")
    color_print("Scraping articles from the following URLs:", "blue")
    for i, url in enumerate(DEMO_URLS[:3], 1):  # Use just the first 3 URLs for the direct demo
        print(f"{i}. {url}")
    
    print("\nStarting direct scraping process...")
    start_time = time.time()
    results = pipeline.process_urls(DEMO_URLS[:3])
    elapsed_time = time.time() - start_time
    
    color_print(f"\nScraped {results['processed_count']} out of {results['total_urls']} articles", "green")
    color_print(f"Processing time: {elapsed_time:.2f} seconds", "blue")
    
    # Part 2: File-based URL processing
    color_print("\nPart 2: File-Based URL Processing", "bold")
    
    # Check if urls.txt exists, create it if not
    if not os.path.exists("urls.txt"):
        color_print("Creating sample urls.txt file...", "yellow")
        with open("urls.txt", "w") as f:
            f.write("# Sample URLs for AI News Scraper\n")
            f.write("# Lines starting with # are ignored as comments\n\n")
            for url in DEMO_URLS[3:6]:  # Use the next 3 URLs
                f.write(f"{url}\n")
        color_print("Created urls.txt with sample URLs", "green")
    
    color_print("Reading URLs from urls.txt file:", "blue")
    from src.main import read_urls_from_file
    file_urls = read_urls_from_file("urls.txt")
    for i, url in enumerate(file_urls[:3], 1):  # Show just the first 3 URLs for brevity
        print(f"{i}. {url}")
    if len(file_urls) > 3:
        print(f"... and {len(file_urls) - 3} more URLs")
    
    print("\nStarting file-based scraping process...")
    start_time = time.time()
    file_results = pipeline.process_urls(file_urls)
    elapsed_time = time.time() - start_time
    
    color_print(f"\nScraped {file_results['processed_count']} out of {file_results['total_urls']} articles from file", "green")
    color_print(f"File processing time: {elapsed_time:.2f} seconds", "blue")
    
    return results["success"] and file_results["success"]


def demo_search(pipeline: NewsPipeline):
    """Demonstrate semantic search."""
    section_header("Semantic Search")
    
    for query in DEMO_SEARCH_QUERIES:
        color_print(f"\nSearching for: '{query}'", "bold")
        results = pipeline.search_articles(query, limit=3)
        
        if not results:
            color_print("No results found.", "yellow")
            continue
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['headline']}")
            print(f"   Relevance: {result['similarity_score']:.4f}")
            print(f"   Source: {result['source_domain']}")
            print(f"   URL: {result['url']}")
            if 'summary' in result:
                print(f"   Summary: {result['summary'][:200]}...")


def demo_listing(pipeline: NewsPipeline):
    """Demonstrate listing all articles."""
    section_header("All Articles")
    
    articles = pipeline.get_all_articles()
    color_print(f"Found {len(articles)} articles in the database:", "blue")
    
    for i, article in enumerate(articles, 1):
        print(f"\n{i}. {article['headline']}")
        print(f"   Source: {article['source_domain']}")
        if 'publish_date' in article and article['publish_date']:
            print(f"   Date: {article['publish_date']}")
        print(f"   URL: {article['url']}")


def run_demo():
    """Run the complete demonstration."""
    color_print("\n🔍 AI NEWS SCRAPER & SEMANTIC SEARCH DEMO 🔍\n", "bold")
    
    # Check environment
    if not check_environment():
        return
    
    # Initialize pipeline with enhanced processing
    pipeline = NewsPipeline(use_enhanced=True)
    
    # Demo: Scraping
    if not demo_scraping(pipeline):
        color_print("Scraping failed! Exiting demo.", "red")
        return
    
    # Demo: Search
    demo_search(pipeline)
    
    # Demo: Listing
    demo_listing(pipeline)
    
    # Conclusion
    section_header("Demo Complete")
    color_print("The AI News Scraper demonstration is complete!", "green")
    color_print("You can now use the application with your own URLs and queries.", "blue")
    color_print("\nSuggested next steps:", "bold")
    color_print("1. Run 'poetry run python cli.py --help' to see all available commands", "blue")
    color_print("2. Process your own URLs with 'poetry run python cli.py process --urls YOUR_URL'", "blue")
    color_print("3. Search the database with 'poetry run python cli.py search \"your query\"'", "blue")


if __name__ == "__main__":
    run_demo()
