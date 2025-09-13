"""
Gemini API configuration for PII Detection enhancement
"""

import os

# Default model and generation settings
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.1"))
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "1200"))

# Env var names to try for the API key
API_KEY_ENV_VARS = ("GOOGLE_API_KEY", "GEMINI_API_KEY")


def get_api_key() -> str | None:
	"""Return the Gemini/Google API key from common env var names."""
	for name in API_KEY_ENV_VARS:
		val = os.getenv(name)
		if val and val.strip():
			return val.strip()
	return None

