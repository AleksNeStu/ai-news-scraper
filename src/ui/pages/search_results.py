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
            
            # Display similarity score if available
            if 'similarity' in article:
                st.markdown(f"**Relevance Score:** {article['similarity']:.2f}")
            
            st.markdown("#### Summary")
            st.markdown(article.get('summary', '*No summary available*'))
            
            st.markdown("#### Topics")
            topics = article.get('topics', [])
            
            # Ensure topics is always a list and handle empty or None values
            if not topics or (len(topics) == 1 and (topics[0] == '' or topics[0] == 'None' or topics[0] is None)):
                st.markdown("*No topics available*")
            else:
                st.markdown(', '.join(f"**{topic}**" for topic in topics if topic and topic != 'None'))
            
            # Button to view full article text
            if st.button("View Full Text", key=f"article_{i}"):
                st.markdown("---")
                st.markdown("### Full Article Text")
                
                # Get article text - handle both direct text and potentially nested structures
                article_text = article.get('text', None)
                
                # Display the article text if available
                if article_text and article_text.strip():
                    st.markdown(article_text)
                else:
                    # If text is not in the main object, try to fetch it from original document
                    st.error("Full text not available in the search results.")
                    st.info("This might be because the article was not fully indexed or the text field was not included in the search results.")


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
            
            # Create horizontal bar chart
            topic_chart = alt.Chart(topics_df).mark_bar().encode(
                x=alt.X('Count:Q', title='Frequency'),
                y=alt.Y('Topic:N', title='Topic', sort='-x'),
                color=alt.Color('Count:Q', scale=alt.Scale(scheme='viridis')),
                tooltip=['Topic', 'Count']
            ).properties(
                title='Most Common Topics',
                height=min(400, len(topics_df) * 30)
            )
            
            st.altair_chart(topic_chart, use_container_width=True)
            
            # Topic co-occurrence matrix (if there are enough topics)
            if len(topic_counts) >= 4:
                st.subheader("Topic Relationships")
                st.write("This visualization shows which topics tend to appear together in the same articles.")
                
                # Create co-occurrence matrix
                from itertools import combinations
                
                topic_pairs = []
                for article in results:
                    article_topics = article.get('topics', [])
                    if len(article_topics) >= 2:
                        for t1, t2 in combinations(article_topics, 2):
                            topic_pairs.append((t1, t2))
                
                # Count pairs
                pair_counts = Counter(topic_pairs)
                
                # Convert to DataFrame for visualization
                if pair_counts:
                    pairs_df = pd.DataFrame([
                        {'Topic1': t1, 'Topic2': t2, 'Count': count} 
                        for (t1, t2), count in pair_counts.most_common(20)
                    ])
                    
                    # Create network graph visualization
                    st.text("Top topic pairs that appear together in articles")
                    st.dataframe(
                        pairs_df,
                        column_config={
                            "Topic1": st.column_config.TextColumn("Topic 1"),
                            "Topic2": st.column_config.TextColumn("Topic 2"),
                            "Count": st.column_config.NumberColumn("Co-occurrences")
                        },
                        hide_index=True
                    )
