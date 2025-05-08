# 📰 AI News Scraper & Semantic Search

## 🎯 Overview
This project creates a Python application that:

- **Scrapes** full news articles (headline + body) from provided URLs
- Uses **GenAI** (OpenAI GPT models) to:
  - Generate concise article summaries
  - Extract relevant topics and keywords
- **Stores** content and metadata in a **vector database**
- Implements **semantic search** for intelligent article retrieval

## 📋 Key Features

### 1️⃣ Article Extraction
- Scrapes **complete news articles** from URLs
- Extracts both **headlines and full text**
- Handles various website formats and error cases
- Implements **advanced error handling** for site-specific issues

### 2️⃣ GenAI Processing
- Generates **concise summaries** (100-300 words)
- Identifies **3-10 key topics** per article
- Uses **predefined topic categories** for consistent classification
- Uses **OpenAI GPT models** for advanced text analysis
- Provides **offline mode** with local model fallbacks

### 3️⃣ Vector Database Integration
- Creates **embeddings** of article content
- Stores **complete metadata** (URL, headline, summary, topics)
- Enables **efficient retrieval** through vector similarity
- Supports **multiple vector database backends**

### 4️⃣ Semantic Search
- Supports **natural language queries**
- Understands **synonyms and context**
- Returns **relevant results** ranked by similarity
- Implements **text-based matching** and **hybrid search**

### 5️⃣ Web Interface & Deployment
- Includes a **Streamlit-based UI** for easy interaction
- Provides **Docker containerization** for simple deployment
- Supports **offline operation** without internet connectivity
- Features **data visualization** for search results and statistics

## 🛠️ Tech Stack

- **Language:** Python 3.9+
- **Package Management:** Poetry
- **Web Scraping:** `newspaper3k`, `BeautifulSoup`
- **GenAI:** OpenAI GPT models
- **Text Processing:** `NLTK` for tokenization and text analysis
- **Vector Database:** FAISS, Qdrant, Pinecone
- **UI:** Streamlit
- **Containerization:** Docker

### NLTK Resources

The application uses the following NLTK resources for text processing:

- **punkt**: For sentence tokenization
- **stopwords**: For filtering common words
- **averaged_perceptron_tagger**: For part-of-speech tagging
- **punkt_tab**: For additional tokenization capabilities

These resources are automatically downloaded on first run to a project-specific `nltk_data` directory, ensuring they're available for both development and deployed environments.

## 📁 Project Structure

The application is built with a modular architecture consisting of the following components:

- `src/scraper.py` – Article scraping using newspaper3k and BeautifulSoup
- `src/summarizer.py` – GenAI-powered text summarization
- `src/topics.py` – Topic extraction and categorization
- `src/embedder.py` – Embedding generation for semantic search
- `src/vector_store.py` – Vector database interactions (FAISS, Qdrant, Pinecone)
- `src/search.py` – Semantic search implementation
- `src/main.py` – Main pipeline orchestration
- `src/config.py` – Configuration and settings

## Installation

### Option 1: Using Docker (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/AleksNeStu/ai-news-scraper.git
cd ai-news-scraper
```

2. Create a `.env` file with your API keys:
```bash
OPENAI_API_KEY=your-openai-api-key
COMPLETION_MODEL=gpt-3.5-turbo
OFFLINE_MODE=false
```

3. Build and run the Docker container:
```bash
docker-compose up -d
```

4. Access the application at http://localhost:8501

### Option 2: Manual Installation

#### Prerequisites

- Python 3.9+
- Poetry (optional, for dependency management)

#### Setup

1. Clone the repository:
```bash
git clone https://github.com/AleksNeStu/ai-news-scraper.git
cd ai-news-scraper
```

2. Install dependencies:

With Poetry (recommended):
```bash
poetry install
```

With pip:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with your API keys and configuration:

```
# OpenAI API Key (required)
OPENAI_API_KEY=your-openai-api-key

# OpenAI Models
EMBEDDING_MODEL=text-embedding-ada-002
COMPLETION_MODEL=gpt-3.5-turbo

# Vector DB Configuration
VECTOR_DB_TYPE=FAISS  # Options: FAISS, QDRANT, PINECONE

# FAISS Configuration (if using FAISS)
FAISS_INDEX_PATH=./data/vector_index

# Qdrant Configuration (if using Qdrant)
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=news_articles

# Pinecone Configuration (if using Pinecone)
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=your-pinecone-environment
PINECONE_INDEX_NAME=news_articles
```

## 💻 Usage

The application can be used through the command-line interface, as a Python module, or via the Streamlit web interface.

### Web Interface (Recommended)

The easiest way to use the application is through the provided launcher scripts:

#### Cross-Platform Launcher Scripts

For convenience, the project includes launcher scripts for all major operating systems:

```bash
# Universal Python launcher (works on all platforms):
python run_app.py

# On Linux/macOS:
./run_app.sh

# On Windows (Command Prompt):
run_app.bat

# On Windows (PowerShell):
.\run_app.ps1
```

These launcher scripts automatically:
- Detect Python installations
- Create and activate virtual environments if needed
- Install dependencies using Poetry or pip
- Launch the Streamlit web interface
- Display version information from git (commit hash, date, branch, message)

#### Version Information Display

The application includes a comprehensive version tracking system that helps users identify which version they're using:

1. **Startup Version Info**: When launching the application through any of the provided scripts, version information from git is displayed in the terminal, showing:
   - Commit hash
   - Commit date and time
   - Current branch
   - Commit message
   - Repository URL (with automatic conversion from SSH to HTTPS URLs)

2. **UI Version Display**: The same version information is available in the Streamlit UI sidebar, with additional features:
   - Clickable links to view the repository
   - Direct links to the specific commit (for GitHub repositories)
   - Formatted with emojis for better readability
   - Expander interface to conserve UI space

3. **Script Organization**: All launcher scripts are organized in the `scripts/` directory with symbolic links in the root directory for convenient access:
   - `run_app.py` - Universal Python launcher (works on all platforms)
   - `run_app.sh` - Bash script for Linux/macOS
   - `run_app.bat` - Batch script for Windows Command Prompt
   - `run_app.ps1` - PowerShell script for modern Windows environments

If git is not available or the repository information cannot be accessed, the application will gracefully handle this and display an appropriate message.

Alternatively, you can start the application manually:

```bash
# Run with Poetry
poetry run streamlit run src/ui/app.py

# Or with regular Python
streamlit run src/ui/app.py
```

This will open a browser window with the application interface, where you can:

- Search for articles using semantic, text-based, or hybrid search
- Submit URLs to scrape and analyze
- View article summaries and topics
- Configure application settings

### Command Line Interface

#### Using the dedicated CLI script

The project includes a user-friendly CLI script (`cli.py`) that provides a more interactive experience:

1. Process news articles:

```bash
# With Poetry - Process URLs directly
poetry run python cli.py process --urls https://example.com/news1 https://example.com/news2

# Process URLs from a text file (one URL per line)
poetry run python cli.py process --file urls.txt

# Without Poetry
python cli.py process --urls https://example.com/news1 https://example.com/news2
```

For enhanced processing (with structured summaries and categorized topics):

```bash
# Enhanced processing with direct URLs
poetry run python cli.py process --urls https://example.com/news1 --enhanced

# Enhanced processing with URLs from a file
poetry run python cli.py process --file urls.txt --enhanced
```

2. Search for articles:

```bash
poetry run python cli.py search "artificial intelligence developments" --limit 5
```

3. List all articles:

```bash
poetry run python cli.py list
```

4. Clear the database:

```bash
poetry run python cli.py clear
```

#### Using the main module directly

You can also use the main module directly:

1. Process news articles:

```bash
# Process URLs directly
poetry run python -m src.main process --urls https://example.com/news1 https://example.com/news2

# Process URLs from a file
poetry run python -m src.main process --file urls.txt
```

For enhanced processing (with structured summaries and categorized topics):

```bash
# Enhanced processing with direct URLs
poetry run python -m src.main process --urls https://example.com/news1 --enhanced

# Enhanced processing with URLs from a file
poetry run python -m src.main process --file urls.txt --enhanced
```

2. Search for articles:

```bash
poetry run python -m src.main search "your search query" --limit 5
```

3. List all articles:

```bash
poetry run python -m src.main list
```

4. Clear the database:

```bash
poetry run python -m src.main clear
```

### Python Module

You can also use the application programmatically:

```python
from src.main import NewsScraperPipeline

# Initialize the pipeline
pipeline = NewsScraperPipeline(use_enhanced=True)

# Process URLs
urls = ["https://example.com/news1", "https://example.com/news2"]
result = pipeline.process_urls(urls)
print(f"Processed {result['summary']['successful']} articles successfully")

# Search for articles
results = pipeline.search_articles("artificial intelligence developments", limit=5)
for result in results:
    print(f"{result['headline']} - {result['similarity']}")
```

### Docker Deployment

The application can be easily deployed using Docker:

```bash
# Build and start the application using docker-compose
docker-compose up -d

# Access the web UI at http://localhost:8501
```

You can customize the deployment by editing the `docker-compose.yml` file to:
- Configure environment variables
- Enable additional vector database services (e.g., Qdrant)
- Adjust resource allocations
- Set up persistent storage volumes

For a quick test, you can also run just the Docker container:

```bash
# Build the Docker image
docker build -t news-scraper .

# Run the container
docker run -p 8501:8501 --env-file .env news-scraper
```

### Offline Mode

The application includes offline mode functionality:

1. **Command Line**: Use the `--offline` flag
   ```bash
   poetry run python cli.py process --urls https://example.com/news1 --offline
   ```

2. **Web UI**: Toggle the "Offline Mode" checkbox in the sidebar

3. **Python Module**: Set `offline_mode=True` when initializing
   ```python
   pipeline = NewsScraperPipeline(config=Config(offline_mode=True))
   ```

In offline mode, the application:
- Uses local embedding models (Sentence Transformers)
- Employs extractive summarization instead of OpenAI
- Performs keyword-based topic extraction
- Uses text-based search with local algorithms
- Requires no internet connection for operation

## 🧪 Testing

Run all tests:

```bash
# With Poetry (recommended)
poetry run pytest

# Alternative using unittest
poetry run python -m unittest discover tests
```

Run specific test file:

```bash
# With Poetry (recommended)
poetry run pytest tests/test_scraper.py

# Alternative using unittest
poetry run python -m unittest tests.test_scraper
```

Run tests with coverage report:

```bash
poetry run pytest --cov=src tests/
```

## 🗄️ Vector Database Options

The application supports three vector databases:

### FAISS (Default)

Facebook AI Similarity Search (FAISS) is included by default and requires no additional setup. It stores indices locally on disk.

### Qdrant

To use Qdrant:
1. Install additional dependencies: 
   ```bash
   poetry install --with optional
   # Or specifically:
   pip install qdrant-client
   ```
2. Set `VECTOR_DB_TYPE=QDRANT` in your .env file
3. Configure `QDRANT_URL` and `QDRANT_COLLECTION_NAME`

### Pinecone

To use Pinecone:
1. Install additional dependencies:
   ```bash
   poetry install --with optional
   # Or specifically:
   pip install pinecone-client
   ```
2. Set `VECTOR_DB_TYPE=PINECONE` in your .env file
3. Configure your Pinecone API key and environment

## 👨‍💻 Development

### Environment Setup

1. Create a development environment:
   ```bash
   # Create and activate virtual environment with Poetry
   poetry env use python
   poetry shell
   ```

2. Install dependencies including development tools:
   ```bash
   poetry install --with dev
   ```

3. Setup pre-commit hooks (optional):
   ```bash
   pre-commit install
   ```

### Project Structure Explained

```
ai-news-scraper/
├── src/                 # Main source code
│   ├── config.py        # Configuration and settings
│   ├── scraper.py       # Article scraping logic
│   ├── summarizer.py    # GenAI summarization
│   ├── topics.py        # Topic extraction
│   ├── embedder.py      # Embedding generation
│   ├── vector_store.py  # Vector DB interactions
│   ├── search.py        # Semantic search logic
│   ├── main.py          # Pipeline orchestration
│   └── ui/              # Streamlit UI components
│       ├── app.py       # Main Streamlit application
│       ├── utils.py     # UI utility functions
│       └── pages/       # UI page components
├── tests/               # Test suite
│   ├── test_scraper.py
│   ├── test_search.py
│   └── ...
├── scripts/             # Cross-platform launcher scripts
│   ├── run_app.py       # Universal Python launcher
│   ├── run_app.sh       # Linux/macOS launcher
│   ├── run_app.bat      # Windows CMD launcher
│   └── run_app.ps1      # Windows PowerShell launcher
├── run_app.py           # Symbolic link to Python launcher
├── run_app.sh           # Symbolic link to Linux/macOS launcher
├── run_app.bat          # Symbolic link to Windows CMD launcher
├── run_app.ps1          # Symbolic link to PowerShell launcher
├── cli.py               # Command-line interface
├── requirements.txt     # Dependencies for pip
├── pyproject.toml       # Poetry configuration
└── README.md            # Project documentation
```

## 🔧 Troubleshooting

### Common Issues

#### UI Navigation Elements Problem

If you see redundant navigation elements in the UI (like "app", "home", "scrape", etc.), this is fixed in the latest version but may happen if you're running an older version of Streamlit.

**Solution**: Update to the latest version of the code or upgrade Streamlit:
```bash
pip install --upgrade streamlit
```

#### Missing lxml.html.clean Module

If you encounter this error:
```
ImportError: lxml.html.clean module is now a separate project lxml_html_clean.
Install lxml[html_clean] or lxml_html_clean directly.
```

**Solution**: Update your dependencies by running:
```bash
pip install "lxml[html_clean]"
# or
poetry add "lxml[html_clean]"
```

#### NLTK Resource Errors

If you encounter errors related to missing NLTK resources, such as:
```
LookupError: Resource punkt_tab not found.
```

**Solution**: The application should automatically download required NLTK resources. If this fails:

1. Manually download the required resources:
```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('averaged_perceptron_tagger'); nltk.download('punkt_tab')"
```

2. Check permissions on the `nltk_data` directory in the project root.

3. If running in Docker, ensure the container has internet access during the build process.

4. Use the provided NLTK resource check script:
```bash
python scripts/check_nltk.py --download
```

5. For debugging, try running with increased logging level:
```bash
python cli.py search "test query" --debug
```

### Network Connectivity Issues

If you experience network connectivity issues, such as:

- Timeouts when trying to access the web interface
- Errors related to API requests (e.g., OpenAI, vector database)

**Solution**:

1. Check your internet connection and ensure you are online.
2. If using Docker, verify that the container has network access.
3. For API-related errors, ensure that your API keys are correctly set in the `.env` file and that the services are reachable.

## 🤝 Contributing

Contributions are welcome! Here's how you can contribute:

1. Fork the repository
2. Create a new branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Run tests: `poetry run pytest`
5. Submit a pull request

Please ensure your code follows the project's coding style and includes appropriate tests.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ✨ Recent Updates

- **NLTK Resource Management**:
  - Added automatic download and management of required NLTK resources
  - Fixed text search functionality by properly handling missing resources
  - Created project-specific NLTK data directory for consistent resource access
  - Added comprehensive tests for NLTK resource handling
- **Organization improvements**:
  - Moved all launcher scripts to a dedicated `scripts/` directory
  - Created symbolic links in the root directory for easier access
  - Made all script files properly executable
- **Version tracking features**:
  - Added version information display that shows git commit details at startup and in the UI
  - Created new `utils.py` with functions to retrieve and display version information
  - Added repository URL and clickable links to view commits in the UI
  - Enhanced version info display with better formatting and emoji support
- **Cross-platform support**:
  - Enhanced universal Python launcher script (`run_app.py`) with version info display
  - Updated existing cross-platform launcher scripts with version info display
  - Ensured proper error handling when git is not available
- **UI Improvements**:
  - Fixed UI navigation issues to remove redundant elements
  - Improved sidebar styling with better visual hierarchy
  - Enhanced version information display with emojis and clear formatting
- **Documentation updates**:
  - Updated README with new file structure information
  - Added troubleshooting section for common issues
  - Improved instructions for all launcher scripts
