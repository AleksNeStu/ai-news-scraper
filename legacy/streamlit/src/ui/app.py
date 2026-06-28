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
from src.enhanced_pipeline import EnhancedNewsScraperPipeline
from src.search import SemanticSearchEngine
from src.vector_store import get_vector_store

# Import UI components
from src.ui.pages.home import render_home_page
from src.ui.pages.search_results import render_search_results, render_visualization
from src.ui.pages.scrape import render_scrape_page
from src.ui.pages.settings import render_settings_page
from src.ui.utils import render_version_info

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
    
    /* Hide the sidebar navigation links that duplicate the radio button functionality */
    ul[data-testid="stSidebarNavItems"] {
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
    st.session_state.enhanced_mode = False  # Default to standard mode
    st.session_state.vector_store = None
    st.session_state.search_engine = None
    st.session_state.articles = []
    st.session_state.search_results = []

def initialize_vector_store(show_errors=True):
    """
    Initialize the vector store and search engine.
    
    Args:
        show_errors: Whether to display error messages in the UI
    
    Returns:
        bool: True if successful, False otherwise
    """
    config = st.session_state.pipeline.config
    try:
        vector_store = get_vector_store()
        search_engine = SemanticSearchEngine(vector_store=vector_store)
        st.session_state.vector_store = vector_store
        st.session_state.search_engine = search_engine
        return True
    except Exception as e:
        if show_errors:
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
    
    # Online/Offline Mode controls with detailed information
    with st.sidebar.expander("🔌 Online/Offline Mode Settings", expanded=True):
        st.markdown("""
        ### Mode Settings
        
        **Online Mode**: 
        - Uses OpenAI API for high-quality embeddings & AI features
        - Requires internet connection & API key
        - Provides better search results and summaries
        
        **Offline Mode**: 
        - Uses local models for all operations
        - Works without internet connection
        - Limited AI capabilities but still functional
        """)
        
        offline_mode = st.checkbox(
            "Enable Offline Mode", 
            value=st.session_state.offline_mode,
            help="Switch between online (OpenAI-powered) and offline (local models) modes"
        )
        
        if offline_mode != st.session_state.offline_mode:
            st.session_state.offline_mode = offline_mode
            st.session_state.pipeline.set_offline_mode(offline_mode)
            st.rerun()
    
    # Enhanced mode toggle
    with st.sidebar.expander("✨ Enhanced Processing Settings", expanded=True):
        st.markdown("""
        ### Enhanced Mode Settings
        
        **Enhanced Mode**: 
        - Uses advanced GenAI capabilities for structured output
        - Provides key points extraction and topic categorization
        - Utilizes more sophisticated prompts for better insights
        - Ideal for detailed analysis of articles
        
        **Standard Mode**: 
        - Uses basic summarization and topic extraction
        - Provides essential information in a simpler format
        - Uses fewer API tokens and faster processing
        """)
        
        enhanced_mode = st.checkbox(
            "Enable Enhanced Mode", 
            value=st.session_state.enhanced_mode,
            help="Switch between enhanced (structured) and standard processing"
        )
        
        if enhanced_mode != st.session_state.enhanced_mode:
            st.session_state.enhanced_mode = enhanced_mode
            
            # Reinitialize pipeline based on mode
            config = Config()
            if enhanced_mode:
                st.session_state.pipeline = EnhancedNewsScraperPipeline(config)
            else:
                st.session_state.pipeline = NewsScraperPipeline(config)
                
            # Update offline mode setting
            st.session_state.pipeline.set_offline_mode(st.session_state.offline_mode)
            st.rerun()
    
    # Status indicators for modes
    status_cols = st.sidebar.columns(2)
    with status_cols[0]:
        if st.session_state.offline_mode:
            st.info("🔌 **OFFLINE MODE**")
        else:
            st.success("🌐 **ONLINE MODE**")
            
    with status_cols[1]:
        if st.session_state.enhanced_mode:
            st.info("✨ **ENHANCED MODE**")
        else:
            st.success("📊 **STANDARD MODE**")
    
    # Display version information at the bottom of the sidebar
    st.sidebar.divider()
    render_version_info()
    
    # Initialize vector store if needed
    if st.session_state.vector_store is None:
        # Track if this is a refresh or initial load
        if "db_initialized" not in st.session_state:
            with st.sidebar.status("Loading vector database...") as status:
                success = initialize_vector_store()
                if success:
                    # Get database metadata
                    db_type = os.environ.get("VECTOR_DB_TYPE", "faiss").upper()
                    
                    # Get specific details based on the database type
                    db_details = ""
                    if db_type == "FAISS":
                        db_path = os.environ.get("FAISS_INDEX_PATH", "data/vector_index")
                        db_details = f"Location: {db_path}"
                    elif db_type == "QDRANT":
                        db_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
                        collection = os.environ.get("QDRANT_COLLECTION_NAME", "news_articles")
                        db_details = f"Server: {db_url}, Collection: {collection}"
                    elif db_type == "PINECONE":
                        env = os.environ.get("PINECONE_ENVIRONMENT", "")
                        index = os.environ.get("PINECONE_INDEX_NAME", "")
                        db_details = f"Environment: {env}, Index: {index}"
                    
                    # Get the number of articles if available
                    article_count = 0
                    if st.session_state.vector_store:
                        try:
                            article_count = len(st.session_state.vector_store.get_all_metadata())
                        except:
                            pass
                    
                    status.update(
                        label=f"{db_type} database loaded successfully! ({article_count} articles)\n{db_details}", 
                        state="complete"
                    )
                    # Mark as initialized to avoid showing message again
                    st.session_state.db_initialized = True
                else:
                    status.update(label="Failed to load vector database!", state="error")
        else:
            # Silent reload on page refresh
            initialize_vector_store(show_errors=False)
    
    # Retrieve/refresh articles for display
    # Always refresh to ensure we have latest data - fixes the counting issue
    if st.session_state.vector_store is not None:
        try:
            articles = st.session_state.vector_store.get_all_articles()
            # Only update if we actually got articles or if the count changed
            if articles or len(articles) != len(st.session_state.get('articles', [])): 
                st.session_state.articles = articles
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
            # First, check if the user wants to clear existing articles
            # Only ask if there are existing articles
            if st.session_state.articles and len(st.session_state.articles) > 0:
                clear_existing = st.radio(
                    "Would you like to clear existing articles before adding new ones?",
                    ["Yes", "No"],
                    index=1  # Default to No
                )
                
                if clear_existing == "Yes":
                    # Clear the vector store
                    if st.session_state.vector_store:
                        success = st.session_state.vector_store.clear()
                        if success:
                            st.success("Successfully cleared existing articles")
                            # Clear the articles list in session state too
                            st.session_state.articles = []
                        else:
                            st.error("Failed to clear existing articles")
            
            # Show pipeline mode information
            if st.session_state.enhanced_mode:
                st.info("✨ Using enhanced pipeline with structured output")
            
            # Process the URLs
            results = []
            for i, url in enumerate(urls):
                st.write(f"Processing: {url}")
                result = st.session_state.pipeline.process_url(
                    url, summarize=summarize, extract_topics=extract_topics
                )
                results.append(result)
                progress_bar.progress((i + 1) / len(urls))
            
            # Refresh articles list after processing
            # Refresh the vector store first
            initialize_vector_store()
            
            # Update article list
            if st.session_state.vector_store:
                st.session_state.articles = st.session_state.vector_store.get_all_articles()
                st.success(f"Successfully processed {len(urls)} URLs. Database now contains {len(st.session_state.articles)} articles.")
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
    
    # Use the appropriate pipeline based on enhanced mode setting
    if st.session_state.enhanced_mode:
        st.session_state.pipeline = EnhancedNewsScraperPipeline(config)
    else:
        st.session_state.pipeline = NewsScraperPipeline(config)
    
    # Set offline mode
    st.session_state.pipeline.set_offline_mode(st.session_state.offline_mode)
    
    # Reset other components to force reinitialization
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