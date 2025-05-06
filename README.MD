# 📰 AI News Scraper & Semantic Search

This project is a Python-based application that:

- Extracts full news articles (headline + body) from provided URLs.
- Generates **summaries** and identifies **key topics** using advanced text analysis.
- Stores articles, summaries, and metadata in a **vector database**.
- Provides a **semantic search** feature that allows users to search articles using natural language queries.

---

## 🚀 Features

- **News Scraping:** Fetches and extracts the full text and title from each article URL.
- **Summarization:** Generates concise summaries of articles.
- **Topic Identification:** Extracts key topics/keywords from each article for easy categorization.
- **Vector Database:** Stores embeddings of articles and metadata for fast semantic querying.
- **Semantic Search:** Allows users to perform natural language searches and retrieves the most relevant articles based on content similarity.

---

## 🛠️ Tech Stack

- **Python 3.9+**
- **Scraping:** `newspaper3k`, `BeautifulSoup`
- **Text Processing:** OpenAI GPT / other GenAI APIs
- **Embeddings:** OpenAI embeddings (e.g., `text-embedding-ada-002`) or SentenceTransformers
- **Vector Database:** FAISS, Pinecone, or Qdrant
- **Semantic Search:** Cosine similarity matching

---

## 📁 Project Structure

