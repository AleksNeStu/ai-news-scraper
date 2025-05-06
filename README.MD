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

- **Language:** Python 3.12+
- **Package Management:** Poetry
- **Web Scraping:** `newspaper3k`, `BeautifulSoup`
- **GenAI:** OpenAI GPT models
- **Embeddings:** OpenAI embedding models (e.g., `text-embedding-ada-002`)
- **Vector DB:** FAISS, Pinecone, or Qdrant
- **Testing:** pytest

## 📁 Project Structure

```
src/
  ├── scraper.py      # Article scraping logic
  ├── summarizer.py   # GenAI summarization
  ├── topics.py       # Topic extraction
  ├── embedder.py     # Embedding generation
  ├── vector_store.py # Vector DB interactions
  ├── search.py       # Semantic search logic
  └── main.py         # Pipeline orchestration
tests/               # Unit and integration tests
```

## 🚀 Installation

### Prerequisites
- Python 3.12+
- Poetry
- OpenAI API key

### Setup
```bash
# Clone repository
git clone https://github.com/yourusername/ai-news-scraper.git
cd ai-news-scraper

# Install dependencies
poetry install

# Set up environment variables
cp .env.example .env
# Edit .env to add your OpenAI API key
```

## 💻 Usage

### Process Articles
```bash
poetry run python src/main.py --urls urls.txt
```

### Search Articles
```bash
poetry run python src/main.py --search "your semantic search query"
```

## 🧪 Testing
```bash
# Run all tests
poetry run pytest

# Run specific test module
poetry run pytest tests/test_scraper.py
```

## 📄 License
[MIT](LICENSE)

