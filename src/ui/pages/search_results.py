"""
Search results page component for the AI News Scraper application.
"""

import streamlit as st
from typing import List, Dict, Any


def render_search_results(results: List[Dict[Any, Any]]):
    """
    Render the search results.
    
    Args:
        results: List of article dictionaries with search results
    """
    if not results:
        st.info("No matching articles found. Try a different search query or adjust your search parameters.")
        return
    
    st.subheader(f"Found {len(results)} articles")
    
    # Group results by topics
    topics_to_articles = {}
    for article in results:
        # Get topics, ensure it's a list, and handle None values
        topics = article.get('topics', [])
        
        # If topics is None or empty, use 'Uncategorized'
        if not topics:
            if 'Uncategorized' not in topics_to_articles:
                topics_to_articles['Uncategorized'] = []
            topics_to_articles['Uncategorized'].append(article)
            # Make sure we set a default empty list for topics if it's None
            article['topics'] = ['Uncategorized']
        else:
            # Process each topic
            for topic in topics:
                if not topic or topic == '' or topic == 'None':
                    topic = 'Uncategorized'
                if topic not in topics_to_articles:
                    topics_to_articles[topic] = []
                topics_to_articles[topic].append(article)
    
    # Create topic filter
    all_topics = list(topics_to_articles.keys())
    if all_topics:
        selected_topics = st.multiselect(
            "Filter by topics",
            options=all_topics,
            default=[]
        )
    else:
        selected_topics = []
    
    # Filter results by selected topics
    filtered_results = results
    if selected_topics:
        filtered_results = [
            article for article in results
            if any(topic in article.get('topics', ['Uncategorized']) for topic in selected_topics)
        ]
    
    # Display filtered results
    for i, article in enumerate(filtered_results):
        with st.expander(f"**{article.get('headline', 'Untitled Article')}**"):
            st.markdown(f"**Source:** [{article.get('url', 'Unknown URL')}]({article.get('url', '#')})")
            
            # Display similarity score if available with improved formatting
            if 'similarity' in article:
                similarity_value = article['similarity']
                if isinstance(similarity_value, dict) and 'score' in similarity_value:
                    similarity_value = similarity_value['score']
                
                # Display the similarity score with better visual indicator
                st.markdown(f"**Relevance Score:** {similarity_value:.4f}")
                
                # Add visual indicator of match quality
                if similarity_value > 0.9:
                    st.success("🎯 Excellent match")
                elif similarity_value > 0.7:
                    st.info("✅ Good match")
                elif similarity_value > 0.5:
                    st.warning("⚠️ Fair match")
                else:
                    st.error("⚠️ Weak match")
            
            st.markdown("#### Topics")
            topics = article.get('topics', [])
            
            # Ensure topics is always a list and handle empty or None values
            if not topics or (len(topics) == 1 and (topics[0] == '' or topics[0] == 'None' or topics[0] is None)):
                st.markdown("*No topics available*")
            else:
                st.markdown(', '.join(f"**{topic}**" for topic in topics if topic and topic != 'None'))
            
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
                        st.info("This might be because the article was not fully indexed or the text field was not included in the search results.")
            
            with article_tabs[2]:
                # Metadata view with better formatting
                st.markdown("### Article Metadata")
                
                # Better timestamp handling with new fields
                import datetime
                
                # Check for article_posted (publication date)
                article_posted = article.get('article_posted', None)
                article_posted_formatted = 'Unknown'
                
                if article_posted:
                    try:
                        if isinstance(article_posted, str) and article_posted != 'Unknown':
                            article_posted_formatted = article_posted
                        # Format consistently if possible
                        if article_posted_formatted.startswith('20') and 'T' in article_posted_formatted:
                            # Try to make ISO format more readable
                            dt = datetime.datetime.fromisoformat(article_posted_formatted.replace('Z', '+00:00'))
                            article_posted_formatted = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
                
                # Check for article_indexed (when added to database)
                article_indexed = article.get('article_indexed', None)
                article_indexed_formatted = 'Unknown'
                
                if article_indexed:
                    try:
                        if isinstance(article_indexed, str) and article_indexed != 'Unknown':
                            article_indexed_formatted = article_indexed
                        # Format consistently if possible
                        if article_indexed_formatted.startswith('20') and 'T' in article_indexed_formatted:
                            # Try to make ISO format more readable
                            dt = datetime.datetime.fromisoformat(article_indexed_formatted.replace('Z', '+00:00'))
                            article_indexed_formatted = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
                
                # Fallback to old timestamp field if new fields aren't available
                if article_posted_formatted == 'Unknown' and article_indexed_formatted == 'Unknown':
                    timestamp = article.get('timestamp', None)
                    formatted_timestamp = 'Unknown'
                    
                    if timestamp:
                        try:
                            # Convert timestamp to readable format if it's a numeric value
                            if isinstance(timestamp, (int, float)) and timestamp > 0:
                                formatted_timestamp = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                            elif isinstance(timestamp, str) and timestamp != 'Unknown':
                                formatted_timestamp = timestamp
                        except Exception as e:
                            st.caption(f"Error formatting timestamp: {str(e)}")
                else:
                    formatted_timestamp = article_posted_formatted
                
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
                    st.markdown(f"**Published:** {article_posted_formatted}")
                    st.markdown(f"**Indexed:** {article_indexed_formatted}")
                    st.markdown(f"**Word Count:** {word_count}")
                
                    # Format similarity score if available
                    similarity = article.get('similarity', None)
                    if similarity is not None:
                        if isinstance(similarity, dict) and 'score' in similarity:
                            similarity = similarity['score']
                        st.markdown(f"**Relevance Score:** {similarity:.4f}")
                
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
                    "article_posted": article_posted,
                    "article_indexed": article_indexed,
                    "timestamp": article.get('timestamp', None),
                    "topics": article.get('topics', []),
                    "word_count": word_count,
                    "similarity_score": article.get('similarity', 'N/A')
                })


def render_visualization(results: List[Dict[Any, Any]]):
    """
    Render visualizations for the search results.
    
    Args:
        results: List of article dictionaries with search results
    """
    if not results:
        return
    
    import pandas as pd
    import altair as alt
    from collections import Counter
    
    st.subheader("Visualizations")
    
    # Create DataFrame for visualization
    data = []
    for article in results:
        similarity = article.get('similarity', 0)
        # For compatibility with different result formats
        if isinstance(similarity, dict) and 'score' in similarity:
            similarity = similarity['score']
            
        data.append({
            'Title': article.get('headline', 'Untitled')[:30] + ('...' if len(article.get('headline', '')) > 30 else ''),
            'Similarity': float(similarity),
            'Source': article.get('source_domain', 'Unknown'),
            'URL': article.get('url', '#'),
            'Topics': ', '.join(article.get('topics', ['Unknown']))[:50] if article.get('topics') else 'Unknown'
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Create interactive tabs for different visualizations
    tab1, tab2, tab3 = st.tabs(["Relevance Scores", "Source Distribution", "Topic Analysis"])
    
    with tab1:
        # Create bar chart of similarity scores
        if len(df) > 0:
            chart = alt.Chart(df).mark_bar().encode(
                x=alt.X('Similarity:Q', title='Relevance Score', scale=alt.Scale(domain=[0, 1])),
                y=alt.Y('Title:N', title='Article', sort='-x'),
                color=alt.Color('Source:N', title='Source'),
                tooltip=['Title', 'Similarity', 'Source', 'Topics']
            ).properties(
                title='Search Results by Relevance',
                height=min(400, len(df) * 30)
            )
            
            st.altair_chart(chart, use_container_width=True)
    
    with tab2:
        # Group by source domain
        if len(df['Source'].unique()) > 1:
            st.subheader("Results by Source")
            source_counts = df['Source'].value_counts().reset_index()
            source_counts.columns = ['Source', 'Count']
            
            # Create both pie chart and bar chart
            col1, col2 = st.columns(2)
            
            with col1:
                pie = alt.Chart(source_counts).mark_arc().encode(
                    theta=alt.Theta(field="Count", type="quantitative"),
                    color=alt.Color(field="Source", type="nominal"),
                    tooltip=['Source', 'Count']
                ).properties(
                    title='Sources (Pie Chart)',
                    width=200,
                    height=200
                )
                
                st.altair_chart(pie, use_container_width=True)
                
            with col2:
                bar = alt.Chart(source_counts).mark_bar().encode(
                    x=alt.X('Count:Q', title='Number of Articles'),
                    y=alt.Y('Source:N', title='Source', sort='-x'),
                    tooltip=['Source', 'Count']
                ).properties(
                    title='Sources (Bar Chart)',
                    height=min(300, len(source_counts) * 40)
                )
                
                st.altair_chart(bar, use_container_width=True)
    
    with tab3:
        # Common topics
        topics_list = []
        for article in results:
            topics_list.extend(article.get('topics', []))
        
        if topics_list:
            # Count topics
            topic_counts = Counter(topics_list)
            
            # Create DataFrame for topics
            topics_df = pd.DataFrame({
                'Topic': list(topic_counts.keys()),
                'Count': list(topic_counts.values())
            }).sort_values('Count', ascending=False)
            
            # Limit to top 15 topics
            if len(topics_df) > 15:
                topics_df = topics_df.head(15)
            
            # Create bar chart for topics
            topic_chart = alt.Chart(topics_df).mark_bar().encode(
                x=alt.X('Count:Q', title='Number of Articles'),
                y=alt.Y('Topic:N', title='Topic', sort='-x'),
                tooltip=['Topic', 'Count']
            ).properties(
                title='Common Topics in Search Results',
                height=min(400, len(topics_df) * 25)
            )
            
            st.altair_chart(topic_chart, use_container_width=True)
