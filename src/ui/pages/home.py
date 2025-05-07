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
            
            # Create chart with better formatting
            chart = alt.Chart(sources_df).mark_bar().encode(
                x=alt.X('Count:Q', title='Number of Articles'),
                y=alt.Y('Source:N', title='Source Domain', sort='-x'),
                tooltip=['Source', 'Count'],
                text=alt.Text('Count:Q', format='d')  # Add text labels showing count values
            ).properties(
                title='Article Sources',
                height=min(300, len(sources_df) * 30)
            ).mark_bar(
                cornerRadiusBottomRight=3,
                cornerRadiusTopRight=3
            ) + alt.Chart(sources_df).mark_text(
                align='left',
                baseline='middle',
                dx=3,  # Small offset from the end of the bars
                fontSize=12,
                fontWeight='bold'
            ).encode(
                x=alt.X('Count:Q'),
                y=alt.Y('Source:N', sort='-x'),
                text='Count:Q'
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
            
            # Create chart with better formatting
            chart = alt.Chart(topics_df).mark_bar().encode(
                x=alt.X('Count:Q', title='Number of Articles'),
                y=alt.Y('Topic:N', title='Topic', sort='-x'),
                tooltip=['Topic', 'Count'],
                text=alt.Text('Count:Q', format='d')  # Add text labels showing count values
            ).properties(
                title='Popular Topics',
                height=min(300, len(topics_df) * 30)
            ).mark_bar(
                cornerRadiusBottomRight=3,
                cornerRadiusTopRight=3
            ) + alt.Chart(topics_df).mark_text(
                align='left',
                baseline='middle',
                dx=3,  # Small offset from the end of the bars
                fontSize=12,
                fontWeight='bold'
            ).encode(
                x=alt.X('Count:Q'),
                y=alt.Y('Topic:N', sort='-x'),
                text='Count:Q'
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
                
                # Show the article details in tabs for better organization
                article_tabs = st.tabs(["📝 Summary", "📄 Full Text", "🔍 Metadata"])
                
                with article_tabs[0]:
                    # Summary view - with improved fallback
                    summary = article.get('summary', '')
                    if summary and summary.strip():
                        st.markdown(f"### Summary\n{summary}")
                    else:
                        # Try to fetch the summary from the database
                        doc_id = article.get('id', None)
                        if doc_id and 'vector_store' in st.session_state and st.session_state.vector_store:
                            try:
                                # Get the full article data
                                complete_article = st.session_state.vector_store.get_article_by_id(doc_id)
                                if complete_article and 'summary' in complete_article and complete_article['summary'].strip():
                                    st.markdown(f"### Summary\n{complete_article['summary']}")
                                else:
                                    st.info("💡 No summary available for this article.")
                            except Exception as e:
                                st.info("💡 No summary available for this article.")
                                st.caption(f"Error retrieving summary: {str(e)}")
                        else:
                            st.info("💡 No summary available for this article.")
                
                with article_tabs[1]:
                    # Full text view with better formatting
                    article_text = article.get('text', '')
                    
                    # Display the article text if available with a container for better styling
                    if article_text and article_text.strip():
                        st.markdown("### Full Article Text")
                        with st.container():
                            st.markdown(article_text)
                    else:
                        # Try to fetch the text using document ID if available
                        doc_id = article.get('id', None)
                        if doc_id and 'vector_store' in st.session_state and st.session_state.vector_store:
                            with st.spinner("Retrieving full text from database..."):
                                try:
                                    # Attempt to get complete article data
                                    complete_article = st.session_state.vector_store.get_article_by_id(doc_id)
                                    if complete_article and 'text' in complete_article and complete_article['text'].strip():
                                        st.markdown("### Full Article Text")
                                        with st.container():
                                            st.markdown(complete_article['text'])
                                    else:
                                        st.warning("📄 Full text not available for this article.")
                                except Exception as e:
                                    st.warning("📄 Full text not available for this article.")
                                    st.caption(f"Error: {str(e)}")
                        else:
                            st.warning("📄 Full text not available for this article.")
                
                with article_tabs[2]:
                    # Display additional metadata with better formatting
                    st.markdown("### Article Metadata")
                    
                    # Format timestamp if available
                    timestamp = article.get('timestamp', None)
                    formatted_timestamp = 'Unknown'
                    
                    if timestamp:
                        try:
                            import datetime
                            # Convert timestamp to readable format if it's a numeric value
                            if isinstance(timestamp, (int, float)) and timestamp > 0:
                                formatted_timestamp = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                            elif isinstance(timestamp, str) and timestamp != 'Unknown':
                                formatted_timestamp = timestamp
                        except Exception as e:
                            st.caption(f"Error formatting timestamp: {str(e)}")
                    
                    # Get the text for word count - try to get it from complete article if missing
                    text = article.get('text', '')
                    word_count = 0
                    
                    if not text and 'id' in article and 'vector_store' in st.session_state:
                        try:
                            complete_article = st.session_state.vector_store.get_article_by_id(article['id'])
                            if complete_article and 'text' in complete_article:
                                text = complete_article.get('text', '')
                        except:
                            pass
                    
                    # Calculate word count if we have text
                    if text and isinstance(text, str):
                        word_count = len(text.split())
                    
                    # Create a more readable display with columns
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Basic Information**")
                        st.markdown(f"**Headline:** {article.get('headline', 'Untitled')}")
                        st.markdown(f"**Source Domain:** {article.get('source_domain', 'Unknown')}")
                        st.markdown(f"**Published:** {formatted_timestamp}")
                        st.markdown(f"**Word Count:** {word_count}")
                    
                    with col2:
                        st.markdown("**Topics & Tags**")
                        topics = article.get('topics', [])
                        
                        # First try to get topics from the database if missing
                        if (not topics or len(topics) == 0) and 'id' in article and 'vector_store' in st.session_state:
                            try:
                                complete_article = st.session_state.vector_store.get_article_by_id(article['id'])
                                if complete_article and 'topics' in complete_article:
                                    topics = complete_article.get('topics', [])
                            except:
                                pass
                        
                        # Display topics with better formatting
                        if topics and len(topics) > 0:
                            topic_list = []
                            for topic in topics:
                                if topic and topic != 'None' and topic != 'Uncategorized':
                                    topic_list.append(topic)
                                    
                            if topic_list:
                                for topic in topic_list:
                                    st.markdown(f"- {topic}")
                            else:
                                st.markdown("*No specific topics identified*")
                        else:
                            st.markdown("*No topics available*")
                    
                    # Add JSON data display directly in the tab (not using expander)
                    st.markdown("**Raw Data (JSON)**")
                    st.json({
                        "headline": article.get('headline', 'Untitled'),
                        "source_domain": article.get('source_domain', 'Unknown'),
                        "url": article.get('url', 'Unknown'),
                        "timestamp": timestamp,
                        "topics": topics,  # Use the potentially updated topics list
                        "word_count": word_count
                    })
                
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
