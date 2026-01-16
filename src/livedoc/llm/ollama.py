"""Ollama LLM client implementation."""

import json
from pathlib import Path
from typing import List, Optional

import ollama

from livedoc.llm.client import BaseLLMClient, LLMError


class OllamaClient(BaseLLMClient):
    """Ollama LLM client implementation.

    Provides access to local Ollama models with vision support.

    Example:
        client = OllamaClient(model="ministral-3-14b")

        # Text-only chat
        response = client.chat("What is the capital of France?")

        # Vision chat with image
        response = client.chat(
            "Describe this image",
            images=[Path("image.png")]
        )

        # JSON mode for structured output
        response = client.chat(
            "Extract entities from this text",
            json_mode=True
        )
    """

    def __init__(self, model: str = "ministral-3-14b"):
        """Initialize the Ollama client.

        Args:
            model: The Ollama model name to use.
        """
        super().__init__(model)

    def chat(
        self,
        prompt: str,
        images: Optional[List[Path]] = None,
        json_mode: bool = False,
    ) -> str:
        """Send a chat message to Ollama and get a response.

        Args:
            prompt: The user prompt to send.
            images: Optional list of image paths for vision models.
            json_mode: If True, enforce JSON output format.

        Returns:
            The model's response text.

        Raises:
            LLMError: If the Ollama request fails.
        """
        try:
            message = {"role": "user", "content": prompt}

            # Add images for vision models
            if images:
                message["images"] = [str(img) for img in images]

            # Build request kwargs
            kwargs = {
                "model": self._model,
                "messages": [message],
            }

            if json_mode:
                kwargs["format"] = "json"

            response = ollama.chat(**kwargs)
            return response["message"]["content"]

        except ollama.ResponseError as e:
            raise LLMError(f"Ollama response error: {e}", original_error=e)
        except Exception as e:
            raise LLMError(f"Ollama request failed: {e}", original_error=e)

    def chat_json(self, prompt: str, images: Optional[List[Path]] = None) -> dict:
        """Send a chat message and parse the JSON response.

        Convenience method that combines chat with JSON parsing.

        Args:
            prompt: The user prompt to send.
            images: Optional list of image paths for vision models.

        Returns:
            Parsed JSON response as a dictionary.

        Raises:
            LLMError: If the request or JSON parsing fails.
        """
        response_text = self.chat(prompt, images=images, json_mode=True)
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse JSON response: {e}", original_error=e)

    def is_available(self) -> bool:
        """Check if Ollama service is available.

        Returns:
            True if Ollama is reachable and the model exists.
        """
        try:
            # List models to check connectivity
            models = ollama.list()
            model_names = [m.get("name", "") for m in models.get("models", [])]
            # Check if our model (or a variant of it) is available
            return any(self._model in name for name in model_names)
        except Exception:
            return False
