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
        sample_urls = {
            "Technology": [
                "https://www.theguardian.com/technology/2025/may/07/amazon-makes-fundamental-leap-forward-in-robotics-with-device-having-sense-of-touch",
                "https://blog.google/technology/ai/google-ai-updates-april-2025/",
                "https://www.forbes.com/councils/forbestechcouncil/2025/02/03/top-10-technology-trends-for-2025/"
            ],
            "World News": [
                "https://apnews.com/article/05ad77483111bf49ffa14b390f550585",
                "https://www.ft.com/content/49e38ee8-f37e-47da-8ee4-1631175d2224",
                "https://www.theguardian.com/business/live/2025/may/06/trade-war-china-service-sector-uk-eurozone-ford-tariffs-bp-shell-oil-business-live-news"
            ],
            "Science": [
                "https://time.com/7283206/what-trump-proposed-nasa-budget-cuts-mean-for-space-science/",
                "https://www.ft.com/content/ccbbcb4a-992f-426b-ae63-97f2770b1655",
                "https://www.reuters.com/sustainability/climate-energy/why-we-need-scientists-now-more-than-ever-2025-05-07/"
            ],
            "AI & Innovation": [
                "https://www.barrons.com/articles/crowdstrike-stock-layoffs-job-cuts-b55c736d",
                "https://www.anthropic.com/news/ai-for-science-program",
                "https://www.techradar.com/pro/live/google-cloud-next-2025-all-the-news-and-updates-as-it-happens"
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
