"""Pipeline stage abstract base class."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from livedoc.core.context import PipelineContext


class PipelineStage(ABC):
    """Abstract base class for pipeline stages.

    Each stage performs a specific transformation on the pipeline context.
    Stages can be chained together to form a complete processing pipeline.

    Example:
        class MyStage(PipelineStage):
            @property
            def name(self) -> str:
                return "my_stage"

            def execute(self, context: PipelineContext) -> PipelineContext:
                # Process context
                return context
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this stage.

        Returns:
            Stage name used for logging and checkpointing.
        """
        ...

    @abstractmethod
    def execute(self, context: "PipelineContext") -> "PipelineContext":
        """Execute the stage's processing logic.

        Args:
            context: Current pipeline context with state and configuration.

        Returns:
            Updated pipeline context after processing.

        Raises:
            StageError: If processing fails and cannot recover.
        """
        ...

    def should_skip(self, context: "PipelineContext") -> bool:
        """Check if this stage should be skipped.

        Override this method to implement conditional stage execution.

        Args:
            context: Current pipeline context.

        Returns:
            True if the stage should be skipped, False otherwise.
        """
        return False

    def on_error(self, context: "PipelineContext", error: Exception) -> None:
        """Handle errors during stage execution.

        Override this method to implement custom error handling.

        Args:
            context: Current pipeline context.
            error: The exception that occurred.
        """
        pass


class StageError(Exception):
    """Exception raised when a stage fails to process."""

    def __init__(self, stage_name: str, message: str):
        self.stage_name = stage_name
        self.message = message
        super().__init__(f"Stage '{stage_name}' failed: {message}")
