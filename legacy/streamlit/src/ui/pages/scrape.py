"""
Scrape page component for the AI News Scraper application.
"""

import streamlit as st
from typing import Dict, List, Any, Callable

def render_scrape_page(process_urls_callback):
    """
    Render the page for scraping articles.
    
    Args:
        process_urls_callback: Function to call when processing URLs
    """
    st.title("🌐 Scrape New Articles")
    
    # Display mode information specific to scraping functionality
    if st.session_state.offline_mode:
        st.warning("""
        ### 🔌 Scraping in Offline Mode
        - Articles will be scraped but with limited processing
        - Summaries will use simplified algorithms instead of OpenAI
        - Topic extraction will be basic and less accurate
        - Article timestamps will be preserved but AI features limited
        """)
    else:
        st.success("""
        ### 🌐 Scraping in Online Mode 
        - Full AI-powered processing available
        - High-quality summaries generated via OpenAI
        - Accurate topic extraction and classification
        - Complete metadata processing for better search
        """)
    
    # Input method selection
    input_method = st.radio("Input method:", ["Enter URLs", "Upload URL file", "Sample URLs"])
    
    urls = []
    if input_method == "Enter URLs":
        url_input = st.text_area(
            "Enter URLs (one per line):",
            placeholder="https://example.com/article1\nhttps://example.com/article2"
        )
        if url_input:
            urls = [url.strip() for url in url_input.split("\n") if url.strip()]
    
    elif input_method == "Upload URL file":
        uploaded_file = st.file_uploader("Upload a file with URLs (one per line)", type=["txt"])
        if uploaded_file is not None:
            urls = [url.strip().decode("utf-8") for url in uploaded_file.readlines() if url.strip()]
    
    else:  # Sample URLs
        st.info("Select from these sample news articles to try out the application")
        
        # Import sample URLs from the data module
        try:
            # First try the absolute import path (works in development)
            from src.ui.data.sample_urls import SAMPLE_URLS, get_random_sample_urls
        except ImportError:
            # In deployment, we might need to adjust the path
            import sys
            from pathlib import Path
            
            # Add the project root to the path so we can import our modules
            project_root = Path(__file__).parent.parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            try:
                # Try the import again
                from src.ui.data.sample_urls import SAMPLE_URLS, get_random_sample_urls
            except ImportError:
                # If all else fails, define the sample URLs here
                import random
                
                # A fallback collection of sample URLs organized by categories
                SAMPLE_URLS = {
                    "Technology": [
                        "https://techcrunch.com/2023/04/17/anthropic-claude-2-1/",
                        "https://www.wired.com/story/how-to-use-chatgpt-for-coding/"
                    ],
                    "World News": [
                        "https://www.reuters.com/world/europe/ukraine-says-russian-forces-blew-up-nova-kakhovka-dam-2023-06-06/",
                        "https://www.bbc.com/news/world-middle-east-67626746"
                    ],
                    "Science": [
                        "https://www.scientificamerican.com/article/new-wave-of-small-nuclear-reactors-could-revitalize-carbon-free-energy/",
                        "https://www.nature.com/articles/d41586-023-02882-1"
                    ]
                }
                
                def get_random_sample_urls(num_urls: int = 3):
                    """Returns a random selection of sample URLs."""
                    all_urls = []
                    for category_urls in SAMPLE_URLS.values():
                        all_urls.extend(category_urls)
                    
                    if num_urls > len(all_urls):
                        return all_urls
                    
                    return random.sample(all_urls, num_urls)
        
        # Add a button to load random samples
        col1, col2 = st.columns([1, 1])
        with col1:
            selected_category = st.selectbox("Select category", list(SAMPLE_URLS.keys()))
        with col2:
            if st.button("📋 Load Random Sample", key="load_random"):
                # Add 3 random URLs from across categories
                st.session_state.random_urls = get_random_sample_urls(3)
                st.rerun()  # Rerun to reflect changes
        
        # If we have random URLs selected, display them
        if hasattr(st.session_state, 'random_urls') and st.session_state.random_urls:
            st.subheader("Random Sample URLs")
            for url in st.session_state.random_urls:
                if st.checkbox(url, key=f"random_{url}"):
                    if url not in urls:  # Prevent duplicates
                        urls.append(url)
            
            if st.button("Clear Random URLs"):
                st.session_state.random_urls = []
                st.rerun()
                
        # Display category-specific URLs
        st.subheader(f"{selected_category} Articles")
        for url in SAMPLE_URLS[selected_category]:
            if st.checkbox(url, key=f"sample_{url}"):
                if url not in urls:  # Prevent duplicates
                    urls.append(url)
    
    # Show selected URLs
    if urls:
        st.write(f"Selected {len(urls)} URLs:")
        for i, url in enumerate(urls):
            st.write(f"{i+1}. {url}")
    
    # Scraping options
    st.subheader("Processing Options")
    col1, col2 = st.columns(2)
    
    with col1:
        summarize = st.checkbox("Generate summaries", value=True)
    with col2:
        extract_topics = st.checkbox("Extract topics", value=True)
        
    # Show current processing mode information
    mode_cols = st.columns(2)
    
    with mode_cols[0]:
        if st.session_state.offline_mode:
            st.info("🔌 **OFFLINE MODE**: Using local models")
            
            if summarize or extract_topics:
                st.warning("⚠️ AI features will use local models with reduced quality.")
        else:
            st.success("🌐 **ONLINE MODE**: Using OpenAI API")
    
    with mode_cols[1]:
        if st.session_state.enhanced_mode:
            st.info("✨ **ENHANCED MODE**: Structured output")
            
            if st.session_state.offline_mode:
                st.warning("⚠️ Enhanced features work best with online mode.")
        else:
            st.success("📊 **STANDARD MODE**: Basic processing")
    
    # Process button
    if st.button("Process URLs", type="primary", disabled=len(urls) == 0):
        if process_urls_callback and urls:
            process_urls_callback(urls, summarize, extract_topics)
