"""
Topic extraction module for identifying key topics in news articles using GenAI.

This module leverages OpenAI's GPT models to extract and categorize the main topics
and keywords from news articles, enabling better organization and searchability.
"""

import logging
import json
import re
import nltk
from collections import Counter
from typing import List, Dict, Any, Optional

import openai
from openai import OpenAI
from tqdm import tqdm

from src.config import OPENAI_API_KEY, COMPLETION_MODEL, OFFLINE_MODE
from src.scraper import ScrapedArticle

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client if we have API key and not in offline mode
client = None
if OPENAI_API_KEY and not OFFLINE_MODE:
    client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize NLTK for offline topic extraction
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
except Exception as e:
    logger.warning(f"Error downloading NLTK data: {str(e)}")


class TopicExtractor:
    """Class for extracting topics and keywords from news articles using OpenAI's GPT models."""
    
    def __init__(self, model: str = COMPLETION_MODEL, min_topics: int = 3, max_topics: int = 10, 
                 offline_mode: bool = OFFLINE_MODE):
        """
        Initialize the TopicExtractor.
        
        Args:
            model: The OpenAI model to use for topic extraction
            min_topics: Minimum number of topics to extract
            max_topics: Maximum number of topics to extract
            offline_mode: Whether to use offline topic extraction
        """
        self.model = model
        self.min_topics = min_topics
        self.max_topics = max_topics
        self.offline_mode = offline_mode
        
    def extract_topics(self, article: ScrapedArticle) -> List[str]:
        """
        Extract key topics from a news article.
        
        Args:
            article: ScrapedArticle object containing the article content
            
        Returns:
            List[str]: List of key topics extracted from the article
        """
        # Use offline extraction if in offline mode
        if self.offline_mode:
            return self._extract_offline_topics(article)
            
        # Otherwise use the OpenAI API
        try:
            if not client:
                logger.warning("OpenAI client not initialized, falling back to offline topic extraction")
                return self._extract_offline_topics(article)
                
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
            # Fall back to offline extraction
            logger.info("Falling back to offline topic extraction")
            return self._extract_offline_topics(article)
    
    def _extract_offline_topics(self, article: ScrapedArticle) -> List[str]:
        """
        Extract topics using offline NLP techniques when no API is available.
        
        Args:
            article: ScrapedArticle object
            
        Returns:
            List[str]: Extracted topics
        """
        try:
            from nltk.tokenize import word_tokenize, sent_tokenize
            from nltk.corpus import stopwords
            from nltk.tag import pos_tag
            from nltk.util import ngrams
            
            # Fallback for missing NLTK data
            stop_words = set()
            try:
                stop_words = set(stopwords.words('english'))
            except:
                stop_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", 
                             "to", "for", "with", "by", "about", "as", "of", "is", 
                             "are", "was", "were", "be", "been", "being", "have", "has"}
            
            # Extract text and headline
            text = article.text
            headline = article.headline
            
            # Combine headline and text (giving headline more weight)
            full_text = headline + " " + headline + " " + text
            
            # Tokenize and clean text
            try:
                tokens = word_tokenize(full_text.lower())
            except:
                # Fallback if NLTK tokenization fails
                tokens = full_text.lower().split()
                
            # Remove stopwords and non-alphabetic tokens
            filtered_tokens = [w for w in tokens if w.isalpha() and w not in stop_words and len(w) > 2]
            
            # Extract named entities and noun phrases (as these are good topic candidates)
            topics = set()
            
            # Try POS tagging to identify nouns
            try:
                tagged = pos_tag(filtered_tokens)
                # Extract nouns (NN, NNS, NNP, NNPS)
                nouns = [word for word, pos in tagged if pos.startswith('NN')]
                
                # Count most common nouns
                noun_counter = Counter(nouns)
                topics.update([noun for noun, count in noun_counter.most_common(self.max_topics * 2)])
            except:
                # Fallback if POS tagging fails
                token_counter = Counter(filtered_tokens)
                topics.update([token for token, count in token_counter.most_common(self.max_topics * 2)])
            
            # Try to extract bigrams and trigrams (multi-word topics)
            try:
                # Generate n-grams
                bigrams_list = list(ngrams(filtered_tokens, 2))
                trigrams_list = list(ngrams(filtered_tokens, 3))
                
                # Count and extract most common n-grams
                bigram_counter = Counter(bigrams_list)
                trigram_counter = Counter(trigrams_list)
                
                # Add most common bigrams and trigrams
                for bigram, count in bigram_counter.most_common(self.max_topics):
                    if count > 1:  # Only add if it appears multiple times
                        topics.add(" ".join(bigram))
                        
                for trigram, count in trigram_counter.most_common(min(5, self.max_topics)):
                    if count > 1:  # Only add if it appears multiple times
                        topics.add(" ".join(trigram))
            except:
                # Skip n-grams if they fail
                pass
            
            # Add headline words as they're likely relevant topics
            try:
                headline_tokens = [w for w in word_tokenize(headline.lower()) 
                                  if w.isalpha() and w not in stop_words and len(w) > 2]
                topics.update(headline_tokens[:5])  # Add up to 5 tokens from headline
            except:
                # Skip if headline processing fails
                pass
            
            # Convert to list and limit results
            topic_list = list(topics)
            topic_list = topic_list[:min(len(topic_list), self.max_topics)]
            
            # Capitalize the first letter of each topic
            topic_list = [t.capitalize() for t in topic_list]
            
            logger.info(f"Successfully extracted {len(topic_list)} topics offline for article: '{article.headline}'")
            return topic_list
            
        except Exception as e:
            logger.error(f"Error extracting offline topics: {str(e)}")
            # Last resort: extract single words from headline
            try:
                words = re.findall(r'\b[a-zA-Z]{3,}\b', article.headline)
                return list(set([w.capitalize() for w in words]))[:self.max_topics]
            except:
                return ["News", "Article"]

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
