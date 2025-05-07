"""
Main Streamlit application for the AI News Scraper project.
"""

import os
import subprocess
import sys
import streamlit as st
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config, suppress_external_library_warnings
from src.main import NewsScraperPipeline
from src.search import SemanticSearchEngine
from src.vector_store import get_vector_store

# Import UI components
from src.ui.pages.home import render_home_page
from src.ui.pages.search_results import render_search_results, render_visualization
from src.ui.pages.scrape import render_scrape_page
from src.ui.pages.settings import render_settings_page

# Suppress warnings from external libraries
suppress_external_library_warnings()

# Configure the Streamlit page
st.set_page_config(
    page_title="AI News Scraper",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide the redundant navigation elements in top left using CSS
hide_streamlit_elements = """
<style>
    /* Hide redundant navigation elements */
    .stApp > header {
        display: none !important;
    }
    
    div[data-testid="stToolbar"] {
        display: none !important;
    }
    
    /* Hide the top-left corner app links */
    div[data-testid="stAppViewContainer"] > div[data-testid="collapsedControl"] {
        display: none !important;
    }
    
    div[data-testid="stVerticalBlock"] > div.appview-container div.stSelectbox label {
        display: none !important;
    }
    
    /* Hide empty forms and redundant text */
    label[data-testid="stWidgetLabel"] {
        visibility: visible !important;
    }
    
    /* Hide Streamlit branding */
    footer {
        visibility: hidden;
    }
</style>
"""
st.markdown(hide_streamlit_elements, unsafe_allow_html=True)

# Initialize session state for storing application state
if "pipeline" not in st.session_state:
    config = Config()
    st.session_state.pipeline = NewsScraperPipeline(config)
    st.session_state.offline_mode = config.offline_mode
    st.session_state.vector_store = None
    st.session_state.search_engine = None
    st.session_state.articles = []
    st.session_state.search_results = []

def initialize_vector_store():
    """Initialize the vector store and search engine."""
    config = st.session_state.pipeline.config
    try:
        vector_store = get_vector_store()
        search_engine = SemanticSearchEngine(vector_store=vector_store)
        st.session_state.vector_store = vector_store
        st.session_state.search_engine = search_engine
        return True
    except Exception as e:
        st.error(f"Error initializing vector store: {str(e)}")
        return False

def main():
    """Main application function."""
    st.sidebar.title("📰 AI News Scraper")
    
    # Enhanced sidebar styling
    st.sidebar.markdown("""
    <style>
        div[data-testid="stSidebar"] .css-16idsys {
            font-weight: bold;
        }
        div[data-testid="stRadio"] > label {
            font-weight: bold;
            font-size: 1.1rem;
            margin-top: 10px;
            margin-bottom: 10px;
        }
        div[data-testid="stRadio"] > div {
            margin-top: 5px;
            margin-bottom: 15px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar navigation
    page = st.sidebar.radio("Navigation", ["Home", "Search", "Scrape Articles", "Settings"])
    
    # Check for offline mode
    offline_mode = st.sidebar.checkbox("Offline Mode", value=st.session_state.offline_mode)
    if offline_mode != st.session_state.offline_mode:
        st.session_state.offline_mode = offline_mode
        st.session_state.pipeline.set_offline_mode(offline_mode)
        st.rerun()
    
    # Status indicator for offline mode
    if st.session_state.offline_mode:
        st.sidebar.info("🔌 Offline Mode Active")
    else:
        st.sidebar.success("🌐 Online Mode Active")
    
    # Initialize vector store if needed
    if st.session_state.vector_store is None:
        with st.sidebar.status("Loading vector database..."):
            success = initialize_vector_store()
            if success:
                st.sidebar.success("Vector database loaded!")
            else:
                st.sidebar.error("Failed to load vector database!")
    
    # Retrieve articles for display if not already loaded
    if not st.session_state.articles and st.session_state.vector_store is not None:
        try:
            st.session_state.articles = st.session_state.vector_store.get_all_articles()
        except Exception as e:
            st.sidebar.error(f"Error retrieving articles: {str(e)}")
    
    # Display the appropriate page content
    if page == "Home":
        article_count = len(st.session_state.articles) if st.session_state.articles else 0
        render_home_page(article_count, st.session_state.articles)
    elif page == "Search":
        render_search_page()
    elif page == "Scrape Articles":
        render_scrape_page(process_urls)
    elif page == "Settings":
        render_settings_page(save_settings)

def process_urls(urls, summarize=True, extract_topics=True):
    """Process a list of URLs through the pipeline."""
    if not urls:
        st.error("No URLs provided")
        return
    
    with st.spinner(f"Processing {len(urls)} URLs..."):
        progress_bar = st.progress(0)
        
        try:
            for i, url in enumerate(urls):
                st.write(f"Processing: {url}")
                st.session_state.pipeline.process_url(
                    url, summarize=summarize, extract_topics=extract_topics
                )
                progress_bar.progress((i + 1) / len(urls))
            
            # Refresh the vector store
            initialize_vector_store()
            
            # Update article list
            if st.session_state.vector_store:
                st.session_state.articles = st.session_state.vector_store.get_all_articles()
                
            st.success(f"Successfully processed {len(urls)} URLs!")
        except Exception as e:
            st.error(f"Error processing URLs: {str(e)}")

def save_settings(settings):
    """Save settings and update components as needed."""
    if not settings:
        return
    
    # Update environment variables
    if "openai_api_key" in settings:
        os.environ["OPENAI_API_KEY"] = settings["openai_api_key"]
    
    # Update vector database settings
    if "vector_db_type" in settings:
        os.environ["VECTOR_DB_TYPE"] = settings["vector_db_type"]
        
        if settings["vector_db_type"] == "faiss" and "faiss_index_path" in settings:
            os.environ["FAISS_INDEX_PATH"] = settings["faiss_index_path"]
        
        elif settings["vector_db_type"] == "qdrant":
            if "qdrant_url" in settings:
                os.environ["QDRANT_URL"] = settings["qdrant_url"]
            if "qdrant_collection_name" in settings:
                os.environ["QDRANT_COLLECTION_NAME"] = settings["qdrant_collection_name"]
        
        elif settings["vector_db_type"] == "pinecone":
            if "pinecone_api_key" in settings:
                os.environ["PINECONE_API_KEY"] = settings["pinecone_api_key"]
            if "pinecone_environment" in settings:
                os.environ["PINECONE_ENVIRONMENT"] = settings["pinecone_environment"]
            if "pinecone_index_name" in settings:
                os.environ["PINECONE_INDEX_NAME"] = settings["pinecone_index_name"]
    
    # Update other settings
    if "local_embedding_model" in settings:
        os.environ["LOCAL_EMBEDDING_MODEL"] = settings["local_embedding_model"]
    
    if "max_retry_attempts" in settings:
        os.environ["MAX_RETRY_ATTEMPTS"] = str(settings["max_retry_attempts"])
    
    if "completion_model" in settings:
        os.environ["COMPLETION_MODEL"] = settings["completion_model"]
    
    # Reinitialize the pipeline with new settings
    config = Config()
    st.session_state.pipeline = NewsScraperPipeline(config)
    st.session_state.vector_store = None
    st.session_state.search_engine = None
    initialize_vector_store()

def render_search_page():
    """Import and render the search page component."""
    from src.ui.pages.search import render_search_page
    render_search_page()

def render_scrape_page(process_callback):
    """Import and render the scrape page component."""
    from src.ui.pages.scrape import render_scrape_page
    render_scrape_page(process_callback)

def render_settings_page(save_callback):
    """Import and render the settings page component."""
    from src.ui.pages.settings import render_settings_page
    render_settings_page(save_callback)



if __name__ == "__main__":
    main()

    # # Check if the script is being run directly or via subprocess
    # if len(sys.argv) > 1 and sys.argv[1] == "run":
    #     # Execute directly when run with 'run' argument
    #     main()
    # else:
    #     # Re-run the script with Streamlit to ensure proper ScriptRunContext
    #     filename = Path(__file__).resolve()
    #     subprocess.run([sys.executable, "-m", "streamlit", "run", str(filename), "--", "run"])