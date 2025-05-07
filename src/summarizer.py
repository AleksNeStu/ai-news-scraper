"""
Summarizer module for generating concise summaries of news articles using GenAI.

This module uses OpenAI's GPT models to generate summaries of news articles.
It focuses on extracting the key points while ensuring the summary is within
the specified length constraints.
"""

import logging
import json
import re
import nltk
from typing import Dict, Any, Optional, List

import openai
from openai import OpenAI
from tqdm import tqdm

from src.config import (
    OPENAI_API_KEY, COMPLETION_MODEL, SUMMARY_MIN_TOKENS, 
    SUMMARY_MAX_TOKENS, OFFLINE_MODE
)
from src.scraper import ScrapedArticle

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client if we have API key and not in offline mode
client = None
if OPENAI_API_KEY and not OFFLINE_MODE:
    client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize NLTK for offline summarization
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except Exception as e:
    logger.warning(f"Error downloading NLTK data: {str(e)}")


class ArticleSummarizer:
    """Class for generating summaries of news articles using OpenAI's GPT models."""
    
    def __init__(self, model: str = COMPLETION_MODEL, 
                 min_tokens: int = SUMMARY_MIN_TOKENS,
                 max_tokens: int = SUMMARY_MAX_TOKENS,
                 offline_mode: bool = OFFLINE_MODE):
        """
        Initialize the ArticleSummarizer.
        
        Args:
            model: The OpenAI model to use for summarization
            min_tokens: Minimum desired token length for summaries
            max_tokens: Maximum desired token length for summaries
            offline_mode: Whether to use offline summarization
        """
        self.model = model
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.offline_mode = offline_mode
        
    def summarize(self, article: ScrapedArticle) -> str:
        """
        Generate a concise summary of the news article.
        
        Args:
            article: ScrapedArticle object containing the article content
            
        Returns:
            str: A concise summary of the article
        """
        # Use offline summarization if in offline mode
        if self.offline_mode:
            return self._generate_offline_summary(article)
            
        # Otherwise use the OpenAI API
        try:
            if not client:
                logger.warning("OpenAI client not initialized, falling back to offline summarization")
                return self._generate_offline_summary(article)
                
            # Build the prompt for summarization
            prompt = self._build_summary_prompt(article)
            
            # Call the OpenAI API for summarization
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional news summarizer. Create concise, "
                                                 "informative summaries that capture the key points of articles."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.5  # Lower temperature for more focused summaries
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info(f"Successfully generated summary for article: '{article.headline}'")
            
            return summary
        
        except Exception as e:
            logger.error(f"Error generating summary for article '{article.headline}': {str(e)}")
            # Fall back to offline summarization
            logger.info("Falling back to offline summarization")
            return self._generate_offline_summary(article)
    
    def _generate_offline_summary(self, article: ScrapedArticle) -> str:
        """
        Generate a summary using offline techniques (extractive summarization).
        
        Args:
            article: ScrapedArticle object containing the article content
            
        Returns:
            str: A summary of the article using extractive summarization
        """
        try:
            # Use extractive summarization (selecting the most important sentences)
            from nltk.tokenize import sent_tokenize
            from nltk.corpus import stopwords
            from nltk.stem import PorterStemmer
            from sklearn.feature_extraction.text import TfidfVectorizer
            
            # Fallback for missing NLTK data
            stop_words = set()
            try:
                stop_words = set(stopwords.words('english'))
            except:
                stop_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with"}
            
            # Extract text from article
            text = article.text
            headline = article.headline
            
            # Tokenize sentences
            sentences = sent_tokenize(text)
            if len(sentences) <= 3:
                # Too short to summarize meaningfully
                if len(text) > 200:
                    return text[:200] + "..."
                return text
            
            # Calculate sentence scores based on TF-IDF
            vectorizer = TfidfVectorizer(stop_words=list(stop_words))
            try:
                tfidf_matrix = vectorizer.fit_transform(sentences)
            except:
                # Fallback if sklearn fails
                return self._simple_extractive_summary(text, headline)
                
            # Calculate sentence scores
            sentence_scores = []
            for i, sentence in enumerate(sentences):
                score = sum(tfidf_matrix[i].toarray()[0])
                words = len(sentence.split())
                if words > 10:  # Ignore very short sentences
                    sentence_scores.append((score, i, sentence))
            
            # Sort by score and select top sentences
            sentence_scores.sort(reverse=True)
            top_sentences = sentence_scores[:min(5, len(sentence_scores))]
            
            # Sort selected sentences by original position
            top_sentences.sort(key=lambda x: x[1])
            
            # Combine sentences into summary
            summary = " ".join([s[2] for s in top_sentences])
            
            # Add headline if not included
            if headline and headline.strip() not in summary:
                summary = headline + ". " + summary
                
            logger.info(f"Successfully generated offline summary for article: '{article.headline}'")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating offline summary: {str(e)}")
            # Last resort fallback
            return self._simple_extractive_summary(article.text, article.headline)
    
    def _simple_extractive_summary(self, text: str, headline: Optional[str] = None) -> str:
        """
        Generate a simple extractive summary by taking the first few sentences.
        
        Args:
            text: Article text
            headline: Article headline
            
        Returns:
            str: Simple summary
        """
        # Split text into sentences using regex (fallback if NLTK fails)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Take first few sentences
        top_sentences = sentences[:min(3, len(sentences))]
        summary = " ".join(top_sentences)
        
        # Add headline if not included
        if headline and headline.strip() not in summary:
            summary = headline + ". " + summary
            
        return summary
    
    def _build_summary_prompt(self, article: ScrapedArticle) -> str:
        """
        Build a prompt for the summarization model.
        
        Args:
            article: ScrapedArticle object containing the article content
            
        Returns:
            str: A formatted prompt for the OpenAI API
        """
        return f"""Please summarize the following news article. 
The summary should be between {self.min_tokens} and {self.max_tokens} tokens long.
Include only the most important information and key points.

Title: {article.headline}

Content:
{article.text[:8000]}  # Limit content to avoid token limits

Your summary:"""

    def summarize_articles(self, articles: list[ScrapedArticle]) -> Dict[str, str]:
        """
        Generate summaries for multiple articles.
        
        Args:
            articles: List of ScrapedArticle objects
            
        Returns:
            Dict[str, str]: A dictionary mapping article URLs to their summaries
        """
        summaries = {}
        
        for article in tqdm(articles, desc="Generating summaries"):
            summary = self.summarize(article)
            summaries[article.url] = summary
            
        return summaries


class EnhancedArticleSummarizer(ArticleSummarizer):
    """Advanced summarizer with structured output format."""
    
    def summarize(self, article: ScrapedArticle) -> Dict[str, Any]:
        """
        Generate a structured summary with key points and takeaways.
        
        Args:
            article: ScrapedArticle object containing the article content
            
        Returns:
            Dict[str, Any]: A dictionary containing the structured summary
        """
        try:
            # Build the prompt for enhanced summarization
            prompt = self._build_enhanced_summary_prompt(article)
            
            # Call the OpenAI API for summarization with JSON output format
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional news summarizer. Create structured "
                                                 "summaries in JSON format with a main summary and key takeaways."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            
            summary_text = response.choices[0].message.content.strip()
            try:
                summary_data = json.loads(summary_text)
                logger.info(f"Successfully generated structured summary for article: '{article.headline}'")
                return summary_data
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response for article '{article.headline}'")
                # Fallback to returning the raw text
                return {"summary": summary_text, "key_points": []}
            
        except Exception as e:
            logger.error(f"Error generating structured summary for article '{article.headline}': {str(e)}")
            return {"summary": "", "key_points": []}
    
    def _build_enhanced_summary_prompt(self, article: ScrapedArticle) -> str:
        """
        Build a prompt for the enhanced summarization model.
        
        Args:
            article: ScrapedArticle object containing the article content
            
        Returns:
            str: A formatted prompt for the OpenAI API
        """
        return f"""Summarize the following news article in a structured JSON format.
Include a concise 'summary' field (between {self.min_tokens//2} and {self.max_tokens//2} tokens) and 
a 'key_points' array containing 3-5 bullet points of the most important information.

Title: {article.headline}

Content:
{article.text[:8000]}  # Limit content to avoid token limits

Respond with a JSON object containing 'summary' and 'key_points' keys."""
