"""
Gemini API client for the ArcVault Triage workflow.

This module provides a simple interface to Google's Gemini API
for text generation and classification tasks.

Features:
- Structured JSON output mode (response_mime_type) for reliable parsing
- Retry with exponential backoff for transient API failures
- Fallback JSON extraction for non-structured responses
"""

import os
import json
import re
import time
import random
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0
MAX_JITTER_SECONDS = 0.5
DEFAULT_FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]


class GeminiClient:
    """
    Client for interacting with Google's Gemini API.

    This client handles API authentication, request formatting,
    response parsing, and retry logic for the triage workflow.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini client.

        Args:
            api_key: Gemini API key. If not provided, reads from GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Import here to allow module to load without API key
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._genai = genai
            configured_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
            fallback_env = os.getenv("GEMINI_FALLBACK_MODELS", "")
            fallback_models = [
                item.strip()
                for item in fallback_env.split(",")
                if item.strip()
            ] or DEFAULT_FALLBACK_MODELS

            # Keep configured model first, then distinct Gemini fallback models.
            self._model_candidates = [configured_model] + [
                model_name
                for model_name in fallback_models
                if model_name != configured_model
            ]
            self._model_index = 0
            self._model_name = self._model_candidates[self._model_index]
            self.model = genai.GenerativeModel(self._model_name)
        except ImportError:
            raise ImportError(
                "google-generativeai package is required. "
                "Install with: pip install google-generativeai"
            )

    def _retry_with_backoff(self, fn, retries: int = MAX_RETRIES):
        """
        Execute a function with exponential backoff on failure.

        Args:
            fn: Callable to execute.
            retries: Maximum number of retry attempts.

        Returns:
            The return value of fn().

        Raises:
            The last exception if all retries are exhausted.
        """
        last_exception = None
        for attempt in range(retries):
            try:
                return fn()
            except Exception as exc:
                last_exception = exc
                if self._switch_model_on_quota_error(exc):
                    continue
                if attempt < retries - 1:
                    delay = max(
                        BASE_DELAY_SECONDS * (2 ** attempt),
                        self._extract_retry_delay_seconds(exc),
                    )
                    jitter = random.uniform(0, MAX_JITTER_SECONDS)
                    time.sleep(delay + jitter)
        raise last_exception

    def _is_quota_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        return (
            "429" in text
            or "quota" in text
            or "rate limit" in text
            or "resource_exhausted" in text
        )

    def _extract_retry_delay_seconds(self, exc: Exception) -> float:
        """Extract suggested retry delay from Gemini error text when available."""
        message = str(exc)
        retry_match = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", message, re.IGNORECASE)
        if retry_match:
            try:
                return float(retry_match.group(1))
            except ValueError:
                return 0.0

        block_match = re.search(r"retry_delay\s*\{[^}]*seconds:\s*([0-9]+)", message)
        if block_match:
            try:
                return float(block_match.group(1))
            except ValueError:
                return 0.0
        return 0.0

    def _switch_model_on_quota_error(self, exc: Exception) -> bool:
        """Switch to next configured Gemini model when current model is quota-limited."""
        if not self._is_quota_error(exc):
            return False
        if self._model_index >= len(self._model_candidates) - 1:
            return False

        self._model_index += 1
        self._model_name = self._model_candidates[self._model_index]
        self.model = self._genai.GenerativeModel(self._model_name)
        return True

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        """
        Generate text using Gemini API with retry logic.

        Args:
            prompt: The prompt to send to the model.
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text response.
        """
        def _call():
            response = self.model.generate_content(
                prompt,
                generation_config=self._genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.1,  # Low temperature for consistent classification
                )
            )
            return response.text

        try:
            return self._retry_with_backoff(_call)
        except Exception as e:
            raise RuntimeError(
                f"Gemini API error after {MAX_RETRIES} attempts on model "
                f"'{self._model_name}': {str(e)}"
            )

    def generate_json(self, prompt: str, max_tokens: int = 1024) -> dict:
        """
        Generate JSON response using Gemini API with structured output mode.

        Uses response_mime_type="application/json" to request structured JSON
        output directly from the model. Falls back to text extraction if
        structured mode fails.

        Args:
            prompt: The prompt to send to the model.
            max_tokens: Maximum tokens in the response.

        Returns:
            Parsed JSON dictionary.

        Raises:
            ValueError: If the response cannot be parsed as JSON.
        """
        # Primary path: use structured JSON output mode
        def _call_structured():
            response = self.model.generate_content(
                prompt,
                generation_config=self._genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.1,
                    response_mime_type="application/json",
                )
            )
            return response.text

        try:
            response_text = self._retry_with_backoff(_call_structured)
            return json.loads(response_text)
        except (json.JSONDecodeError, ValueError):
            pass  # Fall through to text extraction path
        except Exception:
            pass  # Structured mode unavailable, fall through

        # Fallback path: generate as text and extract JSON
        response_text = self.generate(prompt, max_tokens)
        json_str = self._extract_json(response_text)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse JSON response: {str(e)}\n"
                f"Response was: {response_text[:500]}..."
            )

    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from text that may contain markdown or other formatting.

        This is a safety fallback for when structured output mode is unavailable.

        Args:
            text: Text that may contain JSON.

        Returns:
            Extracted JSON string.
        """
        # Remove markdown code blocks if present
        text = text.strip()

        # Handle ```json ... ``` blocks
        if "```json" in text:
            match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
            if match:
                return match.group(1).strip()

        # Handle ``` ... ``` blocks
        if "```" in text:
            match = re.search(r'```\s*([\s\S]*?)\s*```', text)
            if match:
                return match.group(1).strip()

        # Try to find JSON object directly
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return match.group(0)

        # Return as-is if no patterns match
        return text


# Global client instance (initialized lazily)
_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """
    Get or create the global Gemini client instance.

    Returns:
        GeminiClient instance.
    """
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client


def classify_message(message: str, source: str) -> dict:
    """
    Convenience function to classify a message.

    Args:
        message: The customer message to classify.
        source: The source of the message (Email, Web Form, Support Portal).

    Returns:
        Dictionary with category, priority, and confidence.
    """
    from workflow.prompts import CLASSIFICATION_PROMPT

    client = get_gemini_client()
    prompt = CLASSIFICATION_PROMPT.format(message=message, source=source)
    return client.generate_json(prompt)


def enrich_message(message: str, category: str, priority: str) -> dict:
    """
    Convenience function to enrich a message.

    Args:
        message: The customer message.
        category: The classified category.
        priority: The assigned priority.

    Returns:
        Dictionary with core_issue, identifiers, urgency_signal, and human_summary.
    """
    from workflow.prompts import ENRICHMENT_PROMPT

    client = get_gemini_client()
    prompt = ENRICHMENT_PROMPT.format(
        message=message,
        category=category,
        priority=priority
    )
    return client.generate_json(prompt)
