"""
Summarizer module for generating concise summaries of news articles using GenAI.

This module uses OpenAI's GPT models to generate summaries of news articles.
It focuses on extracting the key points while ensuring the summary is within
the specified length constraints.
"""

import logging
import json
from typing import Dict, Any, Optional

import openai
from openai import OpenAI
from tqdm import tqdm

from src.config import OPENAI_API_KEY, COMPLETION_MODEL, SUMMARY_MIN_TOKENS, SUMMARY_MAX_TOKENS
from src.scraper import ScrapedArticle

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


class ArticleSummarizer:
    """Class for generating summaries of news articles using OpenAI's GPT models."""
    
    def __init__(self, model: str = COMPLETION_MODEL, 
                 min_tokens: int = SUMMARY_MIN_TOKENS,
                 max_tokens: int = SUMMARY_MAX_TOKENS):
        """
        Initialize the ArticleSummarizer.
        
        Args:
            model: The OpenAI model to use for summarization
            min_tokens: Minimum desired token length for summaries
            max_tokens: Maximum desired token length for summaries
        """
        self.model = model
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        
    def summarize(self, article: ScrapedArticle) -> str:
        """
        Generate a concise summary of the news article.
        
        Args:
            article: ScrapedArticle object containing the article content
            
        Returns:
            str: A concise summary of the article
        """
        try:
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
            return ""
    
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
