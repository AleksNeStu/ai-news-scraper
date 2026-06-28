"""
Helper module for detecting and handling article parsing errors.
"""

def is_parsing_error(text):
    """
    Detect if the text is an error message from failed parsing.
    
    Args:
        text: The text to check for error patterns
        
    Returns:
        bool: True if text appears to be an error message, False otherwise
    """
    if not text or not isinstance(text, str) or len(text.strip()) < 10:
        return False
        
    # Error phrases that indicate parsing failure
    error_phrases = [
        "I'm sorry", "cannot access", "could not", "wasn't able to", 
        "Error:", "Failed to", "API error", "access denied",
        "cannot assist", "unavailable", "not authorized"
    ]
    
    # Check for common error patterns
    if any(phrase.lower() in text.lower() for phrase in error_phrases):
        # Usually error messages are relatively short
        if len(text.split()) < 100:
            return True
            
    return False
