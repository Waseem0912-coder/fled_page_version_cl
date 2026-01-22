"""vLLM/OpenAI-compatible LLM client implementation."""

import base64
import json
from pathlib import Path
from typing import List, Optional

from livedoc.llm.client import BaseLLMClient, LLMError

try:
    from openai import OpenAI, APIError, APIConnectionError
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None
    APIError = Exception
    APIConnectionError = Exception


class VLLMClient(BaseLLMClient):
    """vLLM/OpenAI-compatible LLM client implementation.

    Provides access to any OpenAI-compatible API (vLLM, text-generation-inference,
    LocalAI, etc.) with vision support.

    Example:
        # Connect to vLLM server
        client = VLLMClient(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            base_url="http://localhost:8000/v1"
        )

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

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "not-needed",
    ):
        """Initialize the vLLM/OpenAI-compatible client.

        Args:
            model: The model name to use.
            base_url: Base URL for the API (e.g., "http://localhost:8000/v1").
            api_key: API key (use "not-needed" for local servers without auth).
        """
        if not OPENAI_AVAILABLE:
            raise LLMError(
                "openai package is required for vLLM support. "
                "Install it with: pip install openai"
            )

        super().__init__(model)
        self._base_url = base_url
        self._api_key = api_key
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def _encode_image(self, image_path: Path) -> str:
        """Encode an image to base64.

        Args:
            image_path: Path to the image file.

        Returns:
            Base64-encoded image string.
        """
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _get_image_media_type(self, image_path: Path) -> str:
        """Get the media type for an image based on extension.

        Args:
            image_path: Path to the image file.

        Returns:
            Media type string (e.g., "image/png").
        """
        suffix = image_path.suffix.lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return media_types.get(suffix, "image/png")

    def chat(
        self,
        prompt: str,
        images: Optional[List[Path]] = None,
        json_mode: bool = False,
    ) -> str:
        """Send a chat message to the vLLM server and get a response.

        Args:
            prompt: The user prompt to send.
            images: Optional list of image paths for vision models.
            json_mode: If True, enforce JSON output format.

        Returns:
            The model's response text.

        Raises:
            LLMError: If the request fails.
        """
        try:
            # Build message content
            if images:
                # Vision request with images
                content = []
                # Add images first
                for image_path in images:
                    base64_image = self._encode_image(image_path)
                    media_type = self._get_image_media_type(image_path)
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{base64_image}"
                        }
                    })
                # Add text prompt
                content.append({"type": "text", "text": prompt})
                messages = [{"role": "user", "content": content}]
            else:
                # Text-only request
                messages = [{"role": "user", "content": prompt}]

            # Build request kwargs
            kwargs = {
                "model": self._model,
                "messages": messages,
            }

            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = self._client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

        except APIConnectionError as e:
            raise LLMError(
                f"Failed to connect to vLLM server at {self._base_url}: {e}",
                original_error=e
            )
        except APIError as e:
            raise LLMError(f"vLLM API error: {e}", original_error=e)
        except Exception as e:
            raise LLMError(f"vLLM request failed: {e}", original_error=e)

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
        """Check if the vLLM server is available.

        Returns:
            True if the server is reachable.
        """
        try:
            # Try to list models to check connectivity
            self._client.models.list()
            return True
        except Exception:
            return False
