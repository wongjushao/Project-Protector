"""
Gemini API Configuration for PII Detection Enhancement
"""

import os

# Gemini API Configuration
CHATGPT_CONFIG = {
    # Model settings
    "model": "gpt-3.5-turbo",  # or "gpt-4" for better accuracy but higher cost
    "max_tokens": 1000,
    "temperature": 0.1,  # Low temperature for consistent results
    
    # Rate limiting
    "max_requests_per_minute": 50,
    "max_tokens_per_minute": 40000,
    
    # Retry settings
    "max_retries": 3,
    "retry_delay": 1.0,  # seconds
    
    # Text processing limits
    "min_text_length": 20,  # Minimum text length to process with Gemini
    "max_text_length": 3000,  # Maximum text length per request
    
    # Confidence thresholds
    "min_confidence": 0.7,  # Minimum confidence to include results
    "consensus_threshold": 0.6,  # Threshold for consensus mechanism
}

# PII Categories that Gemini should focus on
CHATGPT_PII_CATEGORIES = {
    "NAMES": {
        "description": "Personal names, especially Malaysian names with patterns like 'anak', 'bin', 'binti'",
        "examples": ["Ahmad bin Ali", "Ramba anak Sumping", "Siti binti Hassan"],
        "priority": "high"
    },
    "RACES": {
        "description": "Ethnic and racial information",
        "examples": ["Malay", "Chinese", "Indian", "Iban", "Dayak", "Kadazan"],
        "priority": "medium"
    },
    "ORG_NAMES": {
        "description": "Company and organization names",
        "examples": ["ABC Company Sdn Bhd", "Universiti Malaya", "Bank Negara Malaysia"],
        "priority": "medium"
    },
    "STATUS": {
        "description": "Marital and social status information",
        "examples": ["Married", "Single", "Divorced", "Widowed"],
        "priority": "low"
    },
    "LOCATIONS": {
        "description": "Geographic locations and detailed addresses",
        "examples": ["Kuala Lumpur", "Jalan Ampang", "Taman Tun Dr Ismail"],
        "priority": "high"
    },
    "RELIGIONS": {
        "description": "Religious affiliations and beliefs",
        "examples": ["Islam", "Christianity", "Buddhism", "Hinduism"],
        "priority": "low"
    }
}

# Words that should always be ignored (document artifacts)
CHATGPT_IGNORE_WORDS = {
    "malaysia", "kad pengenalan", "identity card", "mykad", "lelaki", "perempuan",
    "warganegara", "copy", "confidential", "draft", "sample", "specimen",
    "watermark", "void", "duplicate", "original", "certified"
}

def get_api_key():
    """Get OpenAI API key from environment variables"""
    return os.getenv('OPENAI_API_KEY')

def is_chatgpt_enabled():
    """Check if ChatGPT integration is enabled"""
    api_key = get_api_key()
    return api_key is not None and len(api_key.strip()) > 0

def get_chatgpt_prompt_template():
    """Get the prompt template for Gemini PII detection"""
    return """You are a PII (Personally Identifiable Information) detection expert specializing in Malaysian documents and cultural context.

Analyze the following text and identify PII entities. Focus ONLY on these categories:
{categories_description}

CRITICAL GUIDELINES:
1. IGNORE these document artifacts: {ignore_words}
2. Focus on Malaysian cultural patterns (names with 'anak', 'bin', 'binti')
3. Always detect: IC numbers, phone numbers, emails, credit cards (these are always sensitive)
4. Be precise - extract actual PII values, not form labels or headers
5. Consider context - distinguish between form labels and actual data

Return ONLY a JSON array with this exact format:
[
  {{"category": "NAMES", "value": "actual name found", "confidence": 0.95}},
  {{"category": "IC", "value": "123456-78-9012", "confidence": 1.0}}
]

Text to analyze:
{text}"""

def get_model_config():
    """Get model configuration for Gemini API calls"""
    return {
        "model": CHATGPT_CONFIG["model"],
        "max_tokens": CHATGPT_CONFIG["max_tokens"],
        "temperature": CHATGPT_CONFIG["temperature"]
    }
