# AI News Scraper & Semantic Search

A Python application that scrapes news articles, uses GenAI to generate summaries and identify topics, and provides semantic search capabilities.

## Features

- 📰 Scrapes complete news articles (headlines and full text) from URLs
- 🤖 Leverages GenAI (OpenAI GPT models) for:
  - Article summarization 
  - Topic extraction and identification
- 🔍 Implements semantic search using vector embeddings
- 📊 Stores articles and metadata in a vector database

## Technology Stack

- Python 3.12+
- Poetry for dependency management
- OpenAI API for GenAI capabilities
- Vector database (FAISS/Qdrant)
- newspaper3k/BeautifulSoup for web scraping

## Installation

### Prerequisites
- Python 3.12+
- Poetry
- OpenAI API key

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ai-news-scraper.git
   cd ai-news-scraper
   ```

2. Install dependencies using Poetry:
   ```bash
   poetry install
   ```

3. Create a `.env` file with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key
   ```

## Usage

### Scrape and Process Articles

```bash
poetry run python src/main.py --urls urls.txt
```

Where `urls.txt` contains a list of URLs to news articles, one per line.

### Search for Articles

```bash
poetry run python src/main.py --search "your search query"
```

This will perform a semantic search against your stored articles and return the most relevant results.

## Project Structure

```
src/
  ├── scraper.py      # Article scraping logic
  ├── summarizer.py   # GenAI summarization
  ├── topics.py       # Topic extraction
  ├── embedder.py     # Embedding generation
  ├── vector_store.py # Vector DB interactions
  ├── search.py       # Semantic search logic
  └── main.py         # Script orchestrating full pipeline
tests/               # Unit and integration tests
```

## License

[MIT](LICENSE)
