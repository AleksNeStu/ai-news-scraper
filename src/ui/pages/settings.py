"""
Settings page component for the AI News Scraper application.
"""

import streamlit as st
import os
from typing import Dict, Any, Callable

def render_settings_page(save_settings_callback: Callable[[Dict[str, Any]], None]):
    """
    Render the settings page.
    
    Args:
        save_settings_callback: Function to call when settings are saved
    """
    st.title("⚙️ Settings")
    
    settings = {}
    settings_changed = False
    
    # API Keys section
    st.subheader("API Keys")
    with st.expander("OpenAI API Key (for AI features)", expanded=True):
        current_api_key = os.environ.get("OPENAI_API_KEY", "")
        hidden_key = "●" * len(current_api_key) if current_api_key else ""
        
        api_key = st.text_input(
            "OpenAI API Key", 
            value=hidden_key,
            type="password",
            help="Your OpenAI API key is required for AI-powered features like summarization and topic extraction."
        )
        
        if api_key and api_key != hidden_key:
            settings["openai_api_key"] = api_key
            settings_changed = True
        
        st.info("If you don't have an API key, you can still use the application in offline mode, but with reduced AI capabilities.")
    
    # Vector Database settings
    st.subheader("Vector Database")
    with st.expander("Database Configuration", expanded=True):
        vector_db_type = st.selectbox(
            "Vector Database Type", 
            ["FAISS", "Qdrant", "Pinecone"],
            index=0,
            help="FAISS is a local vector database that requires no external services. Qdrant and Pinecone require separate setup."
        )
        
        if vector_db_type == "FAISS":
            vector_db_path = st.text_input(
                "FAISS Database Path", 
                value=os.environ.get("FAISS_INDEX_PATH", "data/vector_index"),
                help="Local path where FAISS will store vector embeddings"
            )
            settings["vector_db_type"] = "faiss"
            settings["faiss_index_path"] = vector_db_path
            settings_changed = True
            
        elif vector_db_type == "Qdrant":
            qdrant_url = st.text_input(
                "Qdrant URL",
                value=os.environ.get("QDRANT_URL", "http://localhost:6333"),
                help="URL of your Qdrant server"
            )
            qdrant_collection = st.text_input(
                "Qdrant Collection",
                value=os.environ.get("QDRANT_COLLECTION_NAME", "news_articles"),
                help="Name of the collection in Qdrant"
            )
            settings["vector_db_type"] = "qdrant"
            settings["qdrant_url"] = qdrant_url
            settings["qdrant_collection_name"] = qdrant_collection
            settings_changed = True
            
        elif vector_db_type == "Pinecone":
            pinecone_api_key = st.text_input(
                "Pinecone API Key",
                value="●" * len(os.environ.get("PINECONE_API_KEY", "")),
                type="password",
                help="Your Pinecone API key"
            )
            pinecone_env = st.text_input(
                "Pinecone Environment",
                value=os.environ.get("PINECONE_ENVIRONMENT", "us-west1-gcp"),
                help="Pinecone environment (e.g., us-west1-gcp)"
            )
            pinecone_index = st.text_input(
                "Pinecone Index Name",
                value=os.environ.get("PINECONE_INDEX_NAME", "news-articles"),
                help="Name of your Pinecone index"
            )
            settings["vector_db_type"] = "pinecone"
            settings["pinecone_environment"] = pinecone_env
            settings["pinecone_index_name"] = pinecone_index
            if pinecone_api_key and not all(c == '●' for c in pinecone_api_key):
                settings["pinecone_api_key"] = pinecone_api_key
            settings_changed = True
    
    # Offline Mode settings
    st.subheader("Offline Mode")
    with st.expander("Offline Configuration", expanded=True):
        # Enhanced information about offline mode
        st.markdown("""
        ### About Online/Offline Mode
        
        **Online Mode** *(Default)*:
        - Uses OpenAI API for embeddings, summaries, and topic extraction
        - Provides highest quality results and semantic understanding
        - Requires internet connection and valid API key
        - API usage may incur costs based on OpenAI pricing
        
        **Offline Mode**:
        - Uses local models for all operations (no internet required)
        - Processes articles with Sentence Transformers for embeddings
        - Relies on local algorithms for summaries and topics
        - Reduced quality but works without external dependencies
        - Ideal for air-gapped environments or when API is unavailable
        
        **When to use Offline Mode**:
        - No internet connection available
        - OpenAI API is down or unavailable
        - You've reached API usage limits
        - Processing sensitive content that shouldn't be sent to external APIs
        - Testing or development environments
        """)
        
        current_mode = "OFFLINE" if st.session_state.offline_mode else "ONLINE"
        st.info(f"**Current Mode**: {current_mode}")
        
        offline_model = st.selectbox(
            "Local Embedding Model",
            ["all-MiniLM-L6-v2", "all-mpnet-base-v2", "paraphrase-multilingual-MiniLM-L12-v2"],
            index=0,
            help="Sentence Transformers model for creating embeddings in offline mode"
        )
        settings["local_embedding_model"] = offline_model
        settings_changed = True
        
        st.info("Offline mode can be toggled using the checkbox in the sidebar.")
    
    # Advanced Settings
    st.subheader("Advanced Settings")
    with st.expander("Advanced Configuration"):
        max_retry = st.number_input(
            "Maximum retry attempts for scraping",
            min_value=1,
            max_value=10,
            value=int(os.environ.get("MAX_RETRY_ATTEMPTS", "3")),
            help="Number of times to retry scraping a URL before giving up"
        )
        settings["max_retry_attempts"] = int(max_retry)
        settings_changed = True
        
        completion_model = st.selectbox(
            "OpenAI Completion Model",
            options=["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo-16k", "gpt-4-32k"],
            index=0,
            help="The OpenAI model to use for summarization and topic extraction. More capable models (like GPT-4) will provide better summaries and topic extraction but cost more tokens and may be slower."
        )
        settings["completion_model"] = completion_model
        settings_changed = True
    
    # Save settings
    if st.button("Save Settings", type="primary", disabled=not settings_changed):
        if save_settings_callback:
            save_settings_callback(settings)
            st.success("Settings saved successfully! Some changes may require restarting the application.")
    
    # Database operations
    st.subheader("Database Operations")
    col1, col2 = st.columns(2)
    
    with col1:
        # Initialize state for database clearing confirmation
        if "show_clear_confirm" not in st.session_state:
            st.session_state.show_clear_confirm = False
        
        # Clear Database button
        if not st.session_state.show_clear_confirm and st.button("Clear Database", type="secondary"):
            st.session_state.show_clear_confirm = True
        
        # Show confirmation UI if needed
        if st.session_state.show_clear_confirm:
            st.warning("⚠️ You are about to delete all articles from the database.")
            st.info("This action cannot be undone.")
            
            confirm_col1, confirm_col2 = st.columns(2)
            with confirm_col1:
                if st.button("Yes, clear everything", type="primary"):
                    if st.session_state.get('vector_store'):
                        try:
                            success = st.session_state.vector_store.clear()
                            if success:
                                st.success("✅ Database cleared successfully!")
                                # Reset session state to update UI
                                st.session_state.articles = []
                                st.session_state.search_results = []
                                st.session_state.show_clear_confirm = False
                                # This forces a page refresh to show the empty database
                                st.rerun()
                            else:
                                st.error("❌ Failed to clear database.")
                        except Exception as e:
                            st.error(f"❌ Error clearing database: {str(e)}")
                    else:
                        st.error("Vector database not initialized.")
            
            with confirm_col2:
                if st.button("No, cancel", type="secondary"):
                    st.session_state.show_clear_confirm = False
                    st.rerun()
    
    with col2:
        if st.button("Export Database", type="secondary"):
            if st.session_state.get('vector_store'):
                try:
                    articles = st.session_state.vector_store.get_all_metadata()
                    import json
                    import base64
                    from datetime import datetime
                    
                    # Convert to JSON
                    articles_json = json.dumps(articles, indent=2, default=str)
                    
                    # Generate timestamp for filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"news_articles_{timestamp}.json"
                    
                    # Create download button
                    b64 = base64.b64encode(articles_json.encode()).decode()
                    href = f'<a href="data:file/json;base64,{b64}" download="{filename}">Download JSON</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success(f"✅ {len(articles)} articles exported! Click the link above to download.")
                except Exception as e:
                    st.error(f"❌ Error exporting database: {str(e)}")
            else:
                st.error("Vector database not initialized.")
