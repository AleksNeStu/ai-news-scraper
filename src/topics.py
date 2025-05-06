"""
Topic extraction module for identifying key topics in news articles using GenAI.

This module leverages OpenAI's GPT models to extract and categorize the main topics
and keywords from news articles, enabling better organization and searchability.
"""

import logging
import json
from typing import List, Dict, Any, Optional

import openai
from openai import OpenAI
from tqdm import tqdm

from src.config import OPENAI_API_KEY, COMPLETION_MODEL
from src.scraper import ScrapedArticle

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


class TopicExtractor:
    """Class for extracting topics and keywords from news articles using OpenAI's GPT models."""
    
    def __init__(self, model: str = COMPLETION_MODEL, min_topics: int = 3, max_topics: int = 10):
        """
        Initialize the TopicExtractor.
        
        Args:
            model: The OpenAI model to use for topic extraction
            min_topics: Minimum number of topics to extract
            max_topics: Maximum number of topics to extract
        """
        self.model = model
        self.min_topics = min_topics
        self.max_topics = max_topics
        
    def extract_topics(self, article: ScrapedArticle) -> List[str]:
        """
        Extract key topics from a news article.
        
        Args:
            article: ScrapedArticle object containing the article content
            
        Returns:
            List[str]: List of key topics extracted from the article
        """
        try:
            # Build the prompt for topic extraction
            prompt = self._build_topic_extraction_prompt(article)
            
            # Call the OpenAI API for topic extraction
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a specialist in identifying key topics and themes in text. "
                                                 "Extract the most important topics from news articles."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3  # Lower temperature for more focused, consistent topics
            )
            
            topics_text = response.choices[0].message.content.strip()
            
            # Process the response to extract topics as a list
            topics = self._parse_topics_response(topics_text)
            logger.info(f"Successfully extracted {len(topics)} topics for article: '{article.headline}'")
            
            return topics
        
        except Exception as e:
            logger.error(f"Error extracting topics for article '{article.headline}': {str(e)}")
            return []
    
    def _build_topic_extraction_prompt(self, article: ScrapedArticle) -> str:
        """
        Build a prompt for the topic extraction model.
        
        Args:
            article: ScrapedArticle object containing the article content
            
        Returns:
            str: A formatted prompt for the OpenAI API
        """
        return f"""Extract between {self.min_topics} and {self.max_topics} key topics or themes from the following news article.
Format your response as a list of topics, one per line. Each topic should be a simple phrase of 1-5 words.
Focus on the main subjects, entities, and themes discussed in the article.

Title: {article.headline}

Content:
{article.text[:8000]}  # Limit content to avoid token limits

List of topics (one per line):"""

    def _parse_topics_response(self, response_text: str) -> List[str]:
        """
        Parse the response from the OpenAI API into a list of topics.
        
        Args:
            response_text: The text response from the OpenAI API
            
        Returns:
            List[str]: A list of extracted topics
        """
        # Split by newline and clean up
        lines = response_text.split('\n')
        
        # Process lines to remove numbers, dashes, etc.
        topics = []
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
                
            # Remove numbering and bullet points
            clean_line = line.strip()
            for prefix in ['- ', '* ', '• ', '1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. ', '9. ', '10. ']:
                if clean_line.startswith(prefix):
                    clean_line = clean_line[len(prefix):]
                    break
            
            # Remove quotes if present
            clean_line = clean_line.strip('"\'')
            
            if clean_line:
                topics.append(clean_line)
        
        # Limit to max_topics
        return topics[:self.max_topics]

    def extract_topics_for_articles(self, articles: List[ScrapedArticle]) -> Dict[str, List[str]]:
        """
        Extract topics for multiple articles.
        
        Args:
            articles: List of ScrapedArticle objects
            
        Returns:
            Dict[str, List[str]]: A dictionary mapping article URLs to their extracted topics
        """
        all_topics = {}
        
        for article in tqdm(articles, desc="Extracting topics"):
            topics = self.extract_topics(article)
            all_topics[article.url] = topics
            
        return all_topics


class EnhancedTopicExtractor(TopicExtractor):
    """Advanced topic extractor with structured output and categorization."""
    
    def extract_topics(self, article: ScrapedArticle) -> Dict[str, Any]:
        """
        Extract categorized topics from a news article.
        
        Args:
            article: ScrapedArticle object containing the article content
            
        Returns:
            Dict[str, Any]: A dictionary containing categorized topics
        """
        try:
            # Build the prompt for enhanced topic extraction
            prompt = self._build_enhanced_topic_prompt(article)
            
            # Call the OpenAI API with JSON output format
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a specialist in topic extraction and categorization. "
                                                 "Extract and categorize key topics from news articles in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            topics_text = response.choices[0].message.content.strip()
            
            try:
                topics_data = json.loads(topics_text)
                logger.info(f"Successfully extracted structured topics for article: '{article.headline}'")
                return topics_data
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response for article '{article.headline}'")
                # Fallback to returning a simple format
                return {"topics": self._parse_topics_response(topics_text), "categories": {}}
            
        except Exception as e:
            logger.error(f"Error extracting structured topics for article '{article.headline}': {str(e)}")
            return {"topics": [], "categories": {}}
    
    def _build_enhanced_topic_prompt(self, article: ScrapedArticle) -> str:
        """
        Build a prompt for the enhanced topic extraction model.
        
        Args:
            article: ScrapedArticle object containing the article content
            
        Returns:
            str: A formatted prompt for the OpenAI API
        """
        return f"""Extract and categorize the key topics from the following news article in a structured JSON format.
Include:
1. A 'topics' array with {self.min_topics} to {self.max_topics} important topics
2. A 'categories' object with topics grouped by category (e.g., people, organizations, locations, events, technologies)

Title: {article.headline}

Content:
{article.text[:8000]}  # Limit content to avoid token limits

Respond with a JSON object containing 'topics' and 'categories' keys."""
