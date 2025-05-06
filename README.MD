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

### 2️⃣ GenAI Processing
- Generates **concise summaries** (100-300 words)
- Identifies **3-10 key topics** per article
- Uses **OpenAI GPT models** for advanced text analysis

### 3️⃣ Vector Database Integration
- Creates **embeddings** of article content
- Stores **complete metadata** (URL, headline, summary, topics)
- Enables **efficient retrieval** through vector similarity

### 4️⃣ Semantic Search
- Supports **natural language queries**
- Understands **synonyms and context**
- Returns **relevant results** ranked by similarity

## 🛠️ Tech Stack

- **Language:** Python 3.9+
- **Package Management:** Poetry
- **Web Scraping:** `newspaper3k`, `BeautifulSoup`
- **GenAI:** OpenAI GPT models
- **Embeddings:** OpenAI embedding models (e.g., `text-embedding-ada-002`)
- **Vector DB:** FAISS, Pinecone, or Qdrant
- **Testing:** pytest

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

### Prerequisites

- Python 3.9+
- Poetry (optional, for dependency management)

### Setup

1. Clone the repository:

```
git clone https://github.com/yourusername/ai-news-scraper.git
cd ai-news-scraper
```

2. Install dependencies:

With Poetry (recommended):
```
poetry install
```

With pip:
```
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

The application can be used through the command-line interface or as a Python module.

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
from src.main import NewsPipeline

# Initialize the pipeline
pipeline = NewsPipeline(use_enhanced=True)

# Process URLs
urls = ["https://example.com/news1", "https://example.com/news2"]
result = pipeline.process_urls(urls)
print(f"Processed {result['processed_count']} articles")

# Search for articles
results = pipeline.search_articles("artificial intelligence developments", limit=5)
for result in results:
    print(f"{result['headline']} - {result['similarity_score']}")
```

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

The application supports three vector databases, configurable via the `VECTOR_DB_TYPE` variable in your `.env` file:

- **FAISS** (default):  
  Local, fast, and easy to set up. Stores vector indices on disk.  
  Set in `.env`:  
  ```
  VECTOR_DB_TYPE=FAISS
  FAISS_INDEX_PATH=./data/vector_index
  ```

- **Qdrant**:  
  Open-source, production-ready vector database with REST API.  
  Set in `.env`:  
  ```
  VECTOR_DB_TYPE=QDRANT
  QDRANT_URL=http://localhost:6333
  QDRANT_COLLECTION_NAME=news_articles
  ```

- **Pinecone**:  
  Managed cloud vector database, scalable and robust.  
  Set in `.env`:  
  ```
  VECTOR_DB_TYPE=PINECONE
  PINECONE_API_KEY=your-pinecone-api-key
  PINECONE_ENVIRONMENT=your-pinecone-environment
  PINECONE_INDEX_NAME=news_articles
  ```

### How to Check Database Content

You can inspect the stored articles and metadata using the CLI or Python module:

- **List all articles (CLI):**
  ```bash
  poetry run python cli.py list
  # or
  python cli.py list
  ```

- **Search for articles (CLI):**
  ```bash
  poetry run python cli.py search "your query"
  ```

- **Programmatically (Python):**
  ```python
  from src.main import NewsPipeline
  pipeline = NewsPipeline()
  articles = pipeline.list_articles()
  for article in articles:
      print(article['headline'], article['url'])
  ```

- **Directly (for FAISS):**
  - The FAISS index is stored at the path set by `FAISS_INDEX_PATH`.  
    You can load and inspect it using the FAISS Python API if needed.

- **Directly (for Qdrant):**
  - Use the Qdrant REST API or [Qdrant UI](https://github.com/qdrant/qdrant-ui) to browse collections.

- **Directly (for Pinecone):**
  - Use the Pinecone dashboard or Python client to inspect your index.

**Tip:**  
Always use the provided CLI or Python interfaces for safe access and to avoid corrupting the vector database.

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
│   └── main.py          # Pipeline orchestration
├── tests/               # Test suite
│   ├── test_scraper.py
│   ├── test_search.py
│   └── ...
├── cli.py               # Command-line interface
├── requirements.txt     # Dependencies for pip
├── pyproject.toml       # Poetry configuration
└── README.md            # Project documentation
```

## 🤖 Model Selection

The default models configured for this project are:

- **EMBEDDING_MODEL=text-embedding-ada-002**  
  This OpenAI model provides high-quality vector embeddings suitable for semantic search and topic clustering. It is efficient and widely used for document and query embedding tasks.

- **COMPLETION_MODEL=gpt-3.5-turbo**  
  This model is cost-effective and delivers strong performance for summarization and topic extraction. It is well-suited for generating concise summaries (100–300 words) and extracting key topics from news articles.

These models are appropriate for news article summarization, topic extraction, and semantic search. For even higher quality (and if your budget allows), you may consider upgrading to `gpt-4-turbo` for completion tasks, but `gpt-3.5-turbo` is a solid and reliable default.

## 🔧 Troubleshooting

### Common Issues

#### Missing lxml.html.clean Module

If you encounter this error:
```
ImportError: lxml.html.clean module is now a separate project lxml_html_clean.
Install lxml[html_clean] or lxml_html_clean directly.
```

**Solution**: Update your dependencies by running:
```bash
poetry add "lxml[html_clean]"
# OR with pip
pip install "lxml[html_clean]"
```

#### OpenAI API Authentication Issues

If you see errors related to OpenAI API authentication:

**Solution**: Verify that your .env file contains a valid `OPENAI_API_KEY` entry.

#### Vector Database Connection Errors

**Solution**: If using QDRANT or Pinecone, ensure the service is running and accessible and that your API keys and endpoints are correctly configured in the .env file.

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
