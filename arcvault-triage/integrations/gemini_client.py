"""
Gemini API client for the ArcVault Triage workflow.

This module provides a simple interface to Google's Gemini API
for text generation and classification tasks.
"""

import os
import json
import re
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class GeminiClient:
    """
    Client for interacting with Google's Gemini API.

    This client handles API authentication, request formatting,
    and response parsing for the triage workflow.
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
            # Default to a low-cost fast model.
            # Can be overridden with GEMINI_MODEL env var.
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
            self.model = genai.GenerativeModel(model_name)
            self._genai = genai
            self._model_name = model_name
        except ImportError:
            raise ImportError(
                "google-generativeai package is required. "
                "Install with: pip install google-generativeai"
            )

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        """
        Generate text using Gemini API.

        Args:
            prompt: The prompt to send to the model.
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text response.
        """
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self._genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.1,  # Low temperature for consistent classification
                )
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {str(e)}")

    def generate_json(self, prompt: str, max_tokens: int = 1024) -> dict:
        """
        Generate JSON response using Gemini API.

        This method expects the model to return valid JSON and handles
        extraction and parsing of the JSON from the response.

        Args:
            prompt: The prompt to send to the model.
            max_tokens: Maximum tokens in the response.

        Returns:
            Parsed JSON dictionary.

        Raises:
            ValueError: If the response cannot be parsed as JSON.
        """
        response_text = self.generate(prompt, max_tokens)

        # Try to extract JSON from the response
        # Handle cases where model wraps JSON in markdown code blocks
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
