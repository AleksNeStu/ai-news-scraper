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
        st.info(f"📊 Your database contains {article_count} articles.")
        
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
            
            # Only show top sources if there are many
            if len(sources_df) > 10:
                sources_df = sources_df.head(10)
                sources_df = pd.concat([
                    sources_df, 
                    pd.DataFrame({
                        'Source': ['Other'], 
                        'Count': [article_count - sources_df['Count'].sum()]
                    })
                ])
            
            # Create chart
            chart = alt.Chart(sources_df).mark_bar().encode(
                x=alt.X('Count:Q', title='Number of Articles'),
                y=alt.Y('Source:N', title='Source Domain', sort='-x'),
                tooltip=['Source', 'Count']
            ).properties(
                title='Article Sources',
                height=min(300, len(sources_df) * 30)
            )
            
            st.altair_chart(chart, use_container_width=True)
        
        # Display most common topics
        all_topics = []
        for article in articles:
            all_topics.extend(article.get('topics', []))
        
        # Count topics
        topic_counts = {}
        for topic in all_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        if topic_counts:
            # Convert to DataFrame for charting
            topics_df = pd.DataFrame({
                'Topic': list(topic_counts.keys()),
                'Count': list(topic_counts.values())
            })
            
            # Sort by count
            topics_df = topics_df.sort_values('Count', ascending=False)
            
            # Only show top topics if there are many
            if len(topics_df) > 10:
                topics_df = topics_df.head(10)
            
            # Create chart
            chart = alt.Chart(topics_df).mark_bar().encode(
                x=alt.X('Count:Q', title='Number of Articles'),
                y=alt.Y('Topic:N', title='Topic', sort='-x'),
                tooltip=['Topic', 'Count']
            ).properties(
                title='Popular Topics',
                height=min(300, len(topics_df) * 30)
            )
            
            st.altair_chart(chart, use_container_width=True)
        
        # Show recent articles
        st.subheader("Recent Articles")
        
        # Sort by timestamp (if available) or default to showing first few
        recent_articles = sorted(
            articles, 
            key=lambda x: x.get('timestamp', 0),
            reverse=True
        )[:5]
        
        for i, article in enumerate(recent_articles):
            with st.expander(f"{article.get('headline', 'Untitled Article')}"):
                st.write(f"**Source:** {article.get('url', 'Unknown')}")
                st.write(f"**Summary:** {article.get('summary', 'No summary available')}")
                st.write("**Topics:** " + ', '.join(article.get('topics', ['None'])))
                
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
        
        You can also try the app in offline mode by checking the "Offline Mode" box in the sidebar.
        """)
