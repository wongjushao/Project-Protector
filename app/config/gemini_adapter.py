"""
A tiny adapter around google-generativeai for consistent usage.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
	import google.generativeai as genai
except Exception:  # pragma: no cover - optional import handling
	genai = None  # type: ignore

from .gemini_config import (
	GEMINI_MODEL,
	GEMINI_TEMPERATURE,
	GEMINI_MAX_OUTPUT_TOKENS,
	get_api_key,
)


class GeminiClient:
	def __init__(self, api_key: Optional[str] = None):
		key = api_key or get_api_key()
		if not key:
			raise RuntimeError("Gemini API key not found. Set GOOGLE_API_KEY or GEMINI_API_KEY.")
		if genai is None:
			raise RuntimeError("google-generativeai not installed. Add 'google-generativeai' to requirements.txt")

		genai.configure(api_key=key)
		self.model = genai.GenerativeModel(GEMINI_MODEL)

	def generate_json(self, system_prompt: str, user_prompt: str) -> str:
		"""
		Generate a response intended to be JSON-only. Returns the raw text.
		"""
		content = [
			{"role": "user", "parts": [system_prompt.strip()]},
			{"role": "user", "parts": [user_prompt.strip()]},
		]
		resp = self.model.generate_content(
			content,
			generation_config={
				"temperature": GEMINI_TEMPERATURE,
				"max_output_tokens": GEMINI_MAX_OUTPUT_TOKENS,
				"response_mime_type": "text/plain",
			},
		)
		# google-generativeai returns a response object with .text
		return (resp.text or "").strip()

