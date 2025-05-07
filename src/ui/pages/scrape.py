"""
Scrape page component for the AI News Scraper application.
"""

import streamlit as st
from typing import Dict, List, Any

def render_scrape_page(process_urls_callback):
    """
    Render the page for scraping articles.
    
    Args:
        process_urls_callback: Function to call when processing URLs
    """
    st.title("🌐 Scrape New Articles")
    
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
        sample_urls = {
            "Technology": [
                "https://techcrunch.com/2023/02/13/openai-releases-tool-to-detect-ai-generated-text/",
                "https://www.theverge.com/2023/2/7/23587454/microsoft-bing-edge-chatgpt-ai",
                "https://www.wired.com/story/ai-is-about-to-make-social-media-marketing-really-annoying/"
            ],
            "World News": [
                "https://www.bbc.com/news/world-middle-east-67037529",
                "https://www.reuters.com/world/europe/russian-forces-secure-foothold-eastern-ukraine-vuhledar-2023-02-14/",
                "https://apnews.com/article/g20-india-tensions-ukraine-war-66270f8ae9d852919f1973fde5a8608e"
            ],
            "Science": [
                "https://www.scientificamerican.com/article/nasa-webb-telescope-reveals-new-features-in-jupiters-great-red-spot/",
                "https://www.nature.com/articles/d41586-023-00509-z"
            ]
        }
        
        selected_category = st.selectbox("Select category", list(sample_urls.keys()))
        
        for url in sample_urls[selected_category]:
            if st.checkbox(url, key=f"sample_{url}"):
                urls.append(url)
    
    # Show selected URLs
    if urls:
        st.write(f"Selected {len(urls)} URLs:")
        for i, url in enumerate(urls):
            st.write(f"{i+1}. {url}")
    
    # Scraping options
    st.subheader("Processing Options")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        summarize = st.checkbox("Generate summaries", value=True)
    with col2:
        extract_topics = st.checkbox("Extract topics", value=True)
    with col3:
        offline_mode = st.checkbox("Use offline mode", value=st.session_state.get('offline_mode', False))
        # This is just for the UI, the actual offline mode is controlled by the sidebar
        if offline_mode != st.session_state.get('offline_mode', False):
            st.warning("To change offline mode, use the checkbox in the sidebar")
    
    if offline_mode and (summarize or extract_topics):
        st.warning("⚠️ In offline mode, AI-powered summarization and topic extraction will use local models with reduced quality.")
    
    # Process button
    if st.button("Process URLs", type="primary", disabled=len(urls) == 0):
        if process_urls_callback and urls:
            process_urls_callback(urls, summarize, extract_topics)
