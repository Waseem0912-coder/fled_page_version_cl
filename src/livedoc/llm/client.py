"""LLM client protocol and base class."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM client implementations.

    This protocol defines the interface that all LLM clients must implement.
    Allows for swappable backends (Ollama, OpenAI, Anthropic, etc.).

    Example:
        def process_with_llm(client: LLMClient, prompt: str) -> str:
            return client.chat(prompt)

        # Works with any implementation
        ollama_client = OllamaClient(model="ministral-3-14b")
        result = process_with_llm(ollama_client, "Hello!")
    """

    @property
    def model(self) -> str:
        """The model name being used."""
        ...

    def chat(
        self,
        prompt: str,
        images: Optional[List[Path]] = None,
        json_mode: bool = False,
    ) -> str:
        """Send a chat message and get a response.

        Args:
            prompt: The user prompt to send.
            images: Optional list of image paths for vision models.
            json_mode: If True, enforce JSON output format.

        Returns:
            The model's response text.

        Raises:
            LLMError: If the request fails.
        """
        ...


class BaseLLMClient(ABC):
    """Abstract base class for LLM client implementations.

    Provides common functionality and enforces the LLMClient interface.
    """

    def __init__(self, model: str):
        """Initialize the client.

        Args:
            model: The model name to use.
        """
        self._model = model

    @property
    def model(self) -> str:
        """The model name being used."""
        return self._model

    @abstractmethod
    def chat(
        self,
        prompt: str,
        images: Optional[List[Path]] = None,
        json_mode: bool = False,
    ) -> str:
        """Send a chat message and get a response."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the LLM service is available.

        Returns:
            True if the service is reachable, False otherwise.
        """
        ...


class LLMError(Exception):
    """Exception raised when LLM operations fail."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.original_error = original_error
        super().__init__(message)
