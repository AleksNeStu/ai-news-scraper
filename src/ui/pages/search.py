"""
Search page component for the AI News Scraper application.
"""

import streamlit as st
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

def render_search_page():
    """Render the search page."""
    st.title("🔍 Search Articles")
    
    if st.session_state.vector_store is None:
        st.error("Vector database not initialized. Please check your settings.")
        return
    
    # Create tabs for search types
    tab1, tab2, tab3 = st.tabs(["Semantic Search", "Text Search", "Advanced Search"])
    
    # Tab 1: Semantic Search
    with tab1:
        st.subheader("Semantic Search")
        st.write("Search for articles based on meaning, not just keywords.")
        
        # Search query
        query = st.text_input("Enter your search query:", key="semantic_query")
        
        col1, col2 = st.columns(2)
        with col1:
            limit = st.slider("Number of results", min_value=1, max_value=20, value=5, key="semantic_limit")
        with col2:
            threshold = st.slider("Relevance threshold", min_value=0.0, max_value=1.0, value=0.5, step=0.05, key="semantic_threshold")
        
        # Date filter
        show_date_filter = st.checkbox("Filter by date", key="semantic_date_filter")
        if show_date_filter:
            col1, col2 = st.columns(2)
            with col1:
                days = st.number_input("Show articles from the past (days):", min_value=1, value=30, key="semantic_days")
                date_cutoff = datetime.now() - timedelta(days=days)
            with col2:
                st.write("Date range:")
                st.write(f"From: {date_cutoff.strftime('%Y-%m-%d')} to present")
        else:
            date_cutoff = None
        
        # Domain filter
        filter_domains = st.multiselect(
            "Filter by domains (leave empty for all domains)",
            options=get_unique_domains(),
            default=[],
            key="semantic_domains"
        )
            
        # Search button
        if st.button("Search", type="primary", key="semantic_search_btn") and query:
            perform_search(
                query=query, 
                search_type="semantic", 
                limit=limit, 
                threshold=threshold, 
                filter_domains=filter_domains,
                date_cutoff=date_cutoff
            )
    
    # Tab 2: Text Search
    with tab2:
        st.subheader("Text Search")
        st.write("Find articles containing specific words or phrases.")
        
        # Search query
        query = st.text_input("Enter text to search for:", key="text_query")
        
        col1, col2 = st.columns(2)
        with col1:
            limit = st.slider("Number of results", min_value=1, max_value=50, value=10, key="text_limit")
        with col2:
            match_type = st.selectbox(
                "Match type", 
                ["Contains", "Exact phrase", "All words", "Any word"],
                key="text_match_type"
            )
        
        # Case sensitivity
        case_sensitive = st.checkbox("Case sensitive", key="text_case")
        
        # Domain filter
        filter_domains = st.multiselect(
            "Filter by domains (leave empty for all domains)",
            options=get_unique_domains(),
            default=[],
            key="text_domains"
        )
        
        # Search button
        if st.button("Search", type="primary", key="text_search_btn") and query:
            perform_search(
                query=query, 
                search_type="text", 
                limit=limit, 
                match_type=match_type, 
                case_sensitive=case_sensitive,
                filter_domains=filter_domains
            )
    
    # Tab 3: Advanced Search
    with tab3:
        st.subheader("Advanced Search")
        st.write("Combine semantic understanding with text matching.")
        
        # Search query
        query = st.text_input("Enter your search query:", key="advanced_query")
        
        col1, col2 = st.columns(2)
        
        with col1:
            limit = st.slider("Number of results", min_value=1, max_value=20, value=5, key="advanced_limit")
            threshold = st.slider("Relevance threshold", min_value=0.0, max_value=1.0, value=0.5, step=0.05, key="advanced_threshold")
            
        with col2:
            blend_factor = st.slider(
                "Blend factor", 
                min_value=0.0, 
                max_value=1.0, 
                value=0.5, 
                step=0.1,
                key="advanced_blend",
                help="1.0 = semantic only, 0.0 = text only"
            )
            st.info(f"Using {int(blend_factor*100)}% semantic search, {int((1-blend_factor)*100)}% text search")
        
        # Advanced filters
        st.subheader("Filters")
        col1, col2 = st.columns(2)
        
        with col1:
            filter_domains = st.multiselect(
                "Filter by domains",
                options=get_unique_domains(),
                default=[],
                key="advanced_domains"
            )
        
        with col2:
            topic_filter = st.text_input(
                "Filter by topic (leave empty for all topics)",
                key="advanced_topic"
            )
        
        # Search button
        if st.button("Search", type="primary", key="advanced_search_btn") and query:
            filters = {}
            if filter_domains:
                filters["source_domains"] = filter_domains
            if topic_filter:
                filters["topic"] = topic_filter
                
            perform_search(
                query=query, 
                search_type="hybrid", 
                limit=limit, 
                threshold=threshold, 
                blend=blend_factor,
                filter_criteria=filters
            )
    
    # Display results
    if hasattr(st.session_state, 'search_results') and st.session_state.search_results:
        tab1, tab2 = st.tabs(["Results", "Visualizations"])
        
        with tab1:
            from src.ui.pages.search_results import render_search_results
            render_search_results(st.session_state.search_results)
        
        with tab2:
            from src.ui.pages.search_results import render_visualization
            render_visualization(st.session_state.search_results)


def get_unique_domains():
    """Get a list of unique domain names from the database."""
    if not st.session_state.articles:
        return []
    
    domains = set()
    for article in st.session_state.articles:
        if "source_domain" in article and article["source_domain"]:
            domains.add(article["source_domain"])
    
    return sorted(list(domains))


def perform_search(query, search_type, limit=5, threshold=0.5, blend=0.5, 
                   match_type="Contains", case_sensitive=False, 
                   filter_domains=None, filter_criteria=None, date_cutoff=None):
    """
    Perform a search with the specified parameters.
    
    Args:
        query: Search query
        search_type: Type of search ('semantic', 'text', or 'hybrid')
        limit: Maximum number of results to return
        threshold: Minimum similarity threshold
        blend: Blend factor for hybrid search (1.0 = semantic only)
        match_type: Text match type ('Contains', 'Exact phrase', etc.)
        case_sensitive: Whether text search is case-sensitive
        filter_domains: List of domains to filter by
        filter_criteria: Additional filter criteria
        date_cutoff: Date cutoff for filtering
    """
    try:
        start_time = time.time()
        search_engine = st.session_state.search_engine
        
        # Initialize filter criteria if needed
        if filter_criteria is None:
            filter_criteria = {}
        
        # Add domain filter if specified
        if filter_domains:
            filter_criteria["source_domains"] = filter_domains
            
        # Add date filter if specified
        if date_cutoff:
            filter_criteria["date_cutoff"] = date_cutoff
        
        # Execute search based on selected type
        with st.spinner(f"Searching for '{query}'..."):
            if search_type == "semantic":
                results = search_engine.search(
                    query, 
                    limit=limit, 
                    filter_criteria=filter_criteria,
                    offline_mode=st.session_state.offline_mode
                )
            elif search_type == "text":
                # Adjust parameters based on match type
                case_match = case_sensitive
                exact_match = (match_type == "Exact phrase")
                match_all = (match_type == "All words")
                
                results = search_engine.text_search(
                    query, 
                    limit=limit, 
                    threshold=threshold,
                    exact_match=exact_match,
                    case_match=case_match,
                    match_all=match_all,
                    filter_criteria=filter_criteria
                )
            else:  # Hybrid
                results = search_engine.hybrid_search(
                    query, 
                    limit=limit, 
                    threshold=threshold, 
                    blend=blend,
                    filter_criteria=filter_criteria
                )
        
        # Store results in session state
        st.session_state.search_results = results
        
        # Show search stats
        elapsed_time = time.time() - start_time
        st.success(f"Found {len(results)} results in {elapsed_time:.2f} seconds")
        
    except Exception as e:
        st.error(f"Search error: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
