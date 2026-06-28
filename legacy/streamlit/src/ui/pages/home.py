"""
Home page component for the AI News Scraper application.
"""

import streamlit as st
import altair as alt
import pandas as pd
from typing import Dict, List, Any


def render_home_page(article_count: int, articles: List[Dict[str, Any]]):
    """
    Render the home page of the application.
    
    Args:
        article_count: Number of articles in the database
        articles: List of article dictionaries
    """
    st.title("📰 AI News Scraper & Semantic Search")
    
    # Display current mode information
    if st.session_state.offline_mode:
        st.warning("""
        ### 🔌 Currently in OFFLINE Mode
        - Using local models for embeddings
        - Summarization and topic extraction use simplified algorithms
        - Search capabilities are limited to previously indexed content
        - No API calls will be made to external services
        
        Switch to Online Mode in the sidebar for enhanced features.
        """)
    else:
        st.success("""
        ### 🌐 Currently in ONLINE Mode
        - Using OpenAI for high-quality embeddings and AI features
        - Full summarization and advanced topic extraction available
        - Enhanced semantic search capabilities
        - Ensures best results but requires internet and API keys
        
        Switch to Offline Mode in the sidebar if you don't have internet access.
        """)
    
    st.markdown("""
    Welcome to the AI News Scraper & Semantic Search application! This tool allows you to:
    
    1. 🌐 **Scrape articles** from provided URLs
    2. 🤖 **Generate AI summaries** of the content
    3. 🏷️ **Extract key topics** from each article
    4. 🔍 **Search semantically** through your collection of articles
    
    ### Features:
    
    - **Semantic Search**: Find articles based on meaning, not just keywords
    - **Text-Based Search**: Find exact matches when needed
    - **Hybrid Search**: Combine semantic and text-based approaches
    - **Offline Mode**: Use the app without an internet connection
    - **Docker Support**: Deploy anywhere with containerization
    """)
    
    # Show database statistics
    st.header("Database Statistics")
    
    if article_count > 0:
        # Get all topics and sources for statistics
        all_topics = []
        all_sources = []
        all_urls = []
        successful_parses = 0
        failed_parses = 0
        
        for article in articles:
            # Count successful and failed parses
            if article.get('text') and len(article.get('text', '').strip()) > 20:
                successful_parses += 1
            else:
                failed_parses += 1
                
            # Gather statistics
            all_topics.extend(article.get('topics', []))
            source = article.get('source_domain', 'Unknown')
            if source and source.strip():
                all_sources.append(source)
            url = article.get('url')
            if url:
                all_urls.append(url)
        
        # Filter out None or empty topics
        filtered_topics = [t for t in all_topics if t and t != 'None' and t.strip()]
        unique_topics = set(filtered_topics)
        unique_sources = set(all_sources)
        
        # Create dashboard-like statistics table
        st.info("📊 Database Overview")
        
        # Create a DataFrame for statistics
        stats_data = {
            "Metric": [
                "Articles", 
                "Topics", 
                "Sources", 
                "Successful Parses", 
                "Failed Parses"
            ],
            "Count": [
                article_count,
                len(unique_topics),
                len(unique_sources),
                successful_parses,
                failed_parses
            ]
        }
        
        stats_df = pd.DataFrame(stats_data)
        
        # Display the statistics in a table with styling
        st.dataframe(
            stats_df, 
            use_container_width=True,
            hide_index=True,
            column_config={
                "Metric": st.column_config.TextColumn("Database Metric"),
                "Count": st.column_config.NumberColumn("Count", format="%d")
            }
        )
        
        # Show top topics and sources in smaller tables
        col1, col2 = st.columns(2)
        
        with col1:
            from collections import Counter
            top_topics = Counter(filtered_topics).most_common(5)
            
            if top_topics:
                topics_data = {
                    "Topic": [t[0] for t in top_topics],
                    "Count": [t[1] for t in top_topics]
                }
                topics_df = pd.DataFrame(topics_data)
                
                st.subheader("Top Topics")
                st.dataframe(
                    topics_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Topic": st.column_config.TextColumn("Topic Name"),
                        "Count": st.column_config.NumberColumn("Articles", format="%d")
                    }
                )
        
        with col2:
            top_sources = Counter(all_sources).most_common(5)
            
            if top_sources:
                sources_data = {
                    "Source": [s[0] for s in top_sources],
                    "Count": [s[1] for s in top_sources]
                }
                sources_df = pd.DataFrame(sources_data)
                
                st.subheader("Top Sources")
                st.dataframe(
                    sources_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Source": st.column_config.TextColumn("Domain"),
                        "Count": st.column_config.NumberColumn("Articles", format="%d")
                    }
                )
        
        # Display article source distribution
        sources = {}
        for article in articles:
            source = article.get('source_domain', 'Unknown')
            sources[source] = sources.get(source, 0) + 1
        
        # Convert to DataFrame for charting
        if sources:
            sources_df = pd.DataFrame({
                'Source': list(sources.keys()),
                'Count': list(sources.values())
            })
            
            # Sort by count
            sources_df = sources_df.sort_values('Count', ascending=False)
            
            # Show all sources
            sources_df['Count'] = sources_df['Count'].astype(int)
                
            # Calculate proper height based on number of sources
            source_count = len(sources_df)
            row_height = 40  # Height per row
            chart_height = max(100, min(800, source_count * row_height))
            
            # Create chart with better formatting
            chart = alt.Chart(sources_df).mark_bar().encode(
                x=alt.X('Count:Q', title='Number of Articles', scale=alt.Scale(domain=[0, max(sources_df['Count']) + 1])),
                y=alt.Y('Source:N', 
                       title='Source Domain', 
                       sort='-x',
                       axis=alt.Axis(labelLimit=200)),  # Show full domain names
                tooltip=['Source', 'Count'],
                text=alt.Text('Count:Q', format='d')  # Use integer format
            ).properties(
                title='Article Sources',
                height=chart_height
            ).mark_bar(
                cornerRadiusBottomRight=3,
                cornerRadiusTopRight=3
            ) + alt.Chart(sources_df).mark_text(
                align='left',
                baseline='middle',
                dx=3,
                fontSize=12,
                fontWeight='bold'
            ).encode(
                x=alt.X('Count:Q'),
                y=alt.Y('Source:N', sort='-x'),
                text=alt.Text('Count:Q', format='d')
            )
            
            st.altair_chart(chart, use_container_width=True)
        
        # Display topics
        topic_counter = Counter(filtered_topics)
        
        if topic_counter:
            # Convert to DataFrame for charting
            topics_df = pd.DataFrame({
                'Topic': list(topic_counter.keys()),
                'Count': list(topic_counter.values())
            })
            
            # Sort by count
            topics_df = topics_df.sort_values('Count', ascending=False)
            
            # Show ALL topics with integers
            topics_df['Count'] = topics_df['Count'].astype(int)
            topics_df['Rank'] = range(1, len(topics_df) + 1)
                
            # Adjust chart height
            topic_count = len(topics_df)
            row_height = 40
            chart_height = max(100, min(800, topic_count * row_height))
            
            # Create chart with improved formatting
            chart = alt.Chart(topics_df).mark_bar().encode(
                x=alt.X('Count:Q', title='Number of Articles', scale=alt.Scale(domain=[0, max(topics_df['Count']) + 1])),
                y=alt.Y('Topic:N', title='Topic', sort='-x', axis=alt.Axis(labelLimit=200)),
                tooltip=['Rank', 'Topic', 'Count'],
                text=alt.Text('Count:Q', format='d')
            ).properties(
                title='All Topics',
                height=chart_height
            ).mark_bar(
                cornerRadiusBottomRight=3,
                cornerRadiusTopRight=3
            ) + alt.Chart(topics_df).mark_text(
                align='left',
                baseline='middle',
                dx=3,
                fontSize=12,
                fontWeight='bold'
            ).encode(
                x=alt.X('Count:Q'),
                y=alt.Y('Topic:N', sort='-x'),
                text=alt.Text('Count:Q', format='d')
            )
            
            st.altair_chart(chart, use_container_width=True)
        
        # Show recent and all articles with tabs
        num_recent = min(5, len(articles))
        article_view_tabs = st.tabs([f"Recent Articles ({num_recent})", f"All Articles ({len(articles)})"])
        
        with article_view_tabs[0]:
            # Sort by timestamp
            recent_articles = sorted(
                articles, 
                key=lambda x: x.get('timestamp', 0),
                reverse=True
            )[:num_recent]
            
            if recent_articles:
                st.info(f"Showing {len(recent_articles)} most recent articles from {len(articles)} total articles")
                
                for i, article in enumerate(recent_articles):
                    # Add URL for click-through capability
                    article_url = article.get('url', '')
                    article_headline = article.get('headline', 'Untitled Article')
                    
                    # Create the expandable section with clickable URL
                    with st.expander(f"{article_headline}"):
                        if article_url:
                            st.markdown(f"[🔗 Visit Original Article]({article_url})", unsafe_allow_html=True)
                        
                        # Show the article details in tabs for better organization
                        article_tabs = st.tabs(["📝 Summary", "🏷️ Topics", "📄 Full Text", "🔍 Metadata"])
                        
                        with article_tabs[0]:
                            # Summary view
                            summary = article.get('summary', '')
                            if summary and summary.strip():
                                st.markdown(f"### Summary\n{summary}")
                            else:
                                st.info("💡 No summary available for this article.")
                        
                        with article_tabs[1]:
                            # Topics view
                            st.markdown("### Article Topics")
                            topics = article.get('topics', [])
                            topics = [t for t in topics if t and t != 'None' and t.strip()]
                            
                            if topics:
                                for i, topic in enumerate(topics, 1):
                                    st.markdown(f"**{i}.** {topic}")
                                    
                                if len(topics) > 1:
                                    topic_data = pd.DataFrame({
                                        'Topic': topics,
                                        'Importance': [100 - (i * (100 / len(topics))) for i in range(len(topics))]
                                    })
                                    
                                    topic_chart = alt.Chart(topic_data).mark_bar().encode(
                                        y=alt.Y('Topic:N', sort='-x'),
                                        x=alt.X('Importance:Q', title='Relevance Score'),
                                        color=alt.value('#1f77b4'),
                                        tooltip=['Topic', 'Importance']
                                    ).properties(
                                        height=min(250, len(topics) * 30)
                                    )
                                    
                                    st.altair_chart(topic_chart, use_container_width=True)
                            else:
                                st.info("No topics were extracted for this article.")
                        
                        with article_tabs[2]:
                            # Full text view
                            try:
                                from src.ui.pages.error_handler import is_parsing_error
                            except ImportError:
                                def is_parsing_error(text):
                                    return False
                            
                            article_text = article.get('text', '')
                            
                            if article_text and article_text.strip():
                                # Check for error messages
                                if is_parsing_error(article_text):
                                    st.error("#### Failed to Parse Article")
                                    st.info("This article could not be properly parsed.")
                                    st.code(article_text)
                                else:
                                    st.markdown("### Full Article Text")
                                    with st.container():
                                        st.markdown(article_text)
                            else:
                                st.warning("📄 Full text not available for this article.")
                        
                        with article_tabs[3]:
                            # Metadata view
                            st.markdown("### Article Metadata")
                            
                            # Format and display metadata in columns
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown("**Basic Information**")
                                st.markdown(f"**Headline:** {article.get('headline', 'Untitled')}")
                                st.markdown(f"**Source:** {article.get('source_domain', 'Unknown')}")
                                st.markdown(f"**URL:** {article.get('url', 'Unknown')}")
                            
                            with col2:
                                st.markdown("**Topics & Tags**")
                                topics = article.get('topics', [])
                                if topics and len(topics) > 0:
                                    for topic in topics:
                                        if topic and topic != 'None':
                                            st.markdown(f"- {topic}")
                                else:
                                    st.markdown("*No topics available*")
            else:
                st.info("No articles available. Add articles using the Scrape Articles page.")
        
        with article_view_tabs[1]:
            # Display all articles with pagination
            if articles:
                ARTICLES_PER_PAGE = 10
                
                # Get page number from session state
                if 'article_page' not in st.session_state:
                    st.session_state.article_page = 0
                
                # Calculate total pages
                total_pages = (len(articles) + ARTICLES_PER_PAGE - 1) // ARTICLES_PER_PAGE
                
                # Filter controls
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    sort_options = {
                        "Newest first": lambda x: -x.get('timestamp', 0),
                        "Oldest first": lambda x: x.get('timestamp', 0),
                        "Alphabetical": lambda x: x.get('headline', 'Untitled').lower(),
                    }
                    sort_by = st.selectbox("Sort by:", list(sort_options.keys()), index=0)
                    sorted_articles = sorted(articles, key=sort_options[sort_by])
                
                with col2:
                    page_options = [f"Page {i+1}" for i in range(total_pages)]
                    selected_page = st.selectbox("Go to page:", page_options, index=st.session_state.article_page)
                    st.session_state.article_page = page_options.index(selected_page)
                
                # Get articles for the current page
                start_idx = st.session_state.article_page * ARTICLES_PER_PAGE
                end_idx = min(start_idx + ARTICLES_PER_PAGE, len(sorted_articles))
                
                # Display page information
                st.info(f"Showing articles {start_idx+1} to {end_idx} of {len(articles)} total")
                
                # Display articles in a compact format
                for i, article in enumerate(sorted_articles[start_idx:end_idx]):
                    with st.expander(f"{i+start_idx+1}. {article.get('headline', 'Untitled Article')}"):
                        # Add URL link
                        article_url = article.get('url', '')
                        if article_url:
                            st.markdown(f"[🔗 Visit Original Article]({article_url})", unsafe_allow_html=True)
                        
                        # Show summary and metadata
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            summary = article.get('summary', 'No summary available')
                            if len(summary) > 300:
                                summary = summary[:300] + "..."
                            st.markdown(f"**Summary:** {summary}")
                        
                        with col2:
                            st.markdown(f"**Source:** {article.get('source_domain', 'Unknown')}")
                            
                            # Topics
                            topics = article.get('topics', [])
                            if topics and len(topics) > 0:
                                topics_str = ", ".join(topics[:3])
                                if len(topics) > 3:
                                    topics_str += f" (+{len(topics) - 3} more)"
                                st.markdown(f"**Topics:** {topics_str}")
                
                # Add pagination controls
                cols = st.columns([1, 1, 3, 1, 1])
                
                if st.session_state.article_page > 0:
                    if cols[0].button("⏪ First"):
                        st.session_state.article_page = 0
                        st.rerun()
                    
                    if cols[1].button("◀️ Previous"):
                        st.session_state.article_page -= 1
                        st.rerun()
                
                cols[2].write(f"Page {st.session_state.article_page + 1} of {total_pages}")
                
                if st.session_state.article_page < total_pages - 1:
                    if cols[3].button("Next ▶️"):
                        st.session_state.article_page += 1
                        st.rerun()
                    
                    if cols[4].button("Last ⏩"):
                        st.session_state.article_page = total_pages - 1
                        st.rerun()
            else:
                st.info("No articles available. Add articles using the Scrape Articles page.")
                
                # Show empty state placeholders
                article_tabs = st.tabs(["📝 Summary", "🏷️ Topics", "📄 Full Text", "🔍 Metadata"])
                
                with article_tabs[0]:
                    st.markdown("### Summary")
                    st.info("No articles available. Add articles using the Scrape Articles page.")
                
                with article_tabs[1]:
                    st.markdown("### Article Topics")
                    st.info("No topics available - there are no articles yet.")
                
                with article_tabs[2]:
                    st.markdown("### Full Article Text")
                    st.warning("📄 Full text not available - there are no articles yet.")
                
                with article_tabs[3]:
                    st.markdown("### Article Metadata")
                    st.info("No metadata available - there are no articles yet.")
    else:
        st.warning("Your database is empty. Start by scraping some articles!")
        
        # Show a demo section
        st.subheader("Getting Started")
        st.markdown("""
        To get started with AI News Scraper:
        
        1. Navigate to the **Scrape Articles** tab
        2. Enter one or more news article URLs
        3. Click "Process URLs" to scrape and analyze the articles
        4. Use the **Search** tab to find articles by topic or content
        
        **Advanced Options:**
        - Toggle **Offline Mode** in the sidebar when working without internet
        - Enable **Enhanced Mode** for structured content with key points and topic categories
        - Adjust AI processing settings in the Settings page
        """)
