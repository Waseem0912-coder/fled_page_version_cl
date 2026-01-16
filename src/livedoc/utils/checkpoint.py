"""Checkpoint management for pipeline resumability."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from livedoc.core.context import PipelineContext
    from livedoc.core.document import LiveDocument


class CheckpointManager:
    """Manages saving and loading pipeline checkpoints for resumability.

    Checkpoints allow long-running pipelines to resume from the last
    successfully processed page after interruption.

    Example:
        manager = CheckpointManager(output_dir)

        # Save after each page
        manager.save(context, page_index=5)

        # Load on resume
        if manager.exists():
            data = manager.load()
            # Restore state from data
    """

    CHECKPOINT_FILE = "checkpoint.json"

    def __init__(self, output_dir: Path):
        """Initialize checkpoint manager.

        Args:
            output_dir: Directory for checkpoint files.
        """
        self.output_dir = Path(output_dir)
        self.checkpoint_path = self.output_dir / self.CHECKPOINT_FILE

    def exists(self) -> bool:
        """Check if a checkpoint exists.

        Returns:
            True if checkpoint file exists.
        """
        return self.checkpoint_path.exists()

    def save(
        self,
        context: "PipelineContext",
        page_index: int,
    ) -> None:
        """Save checkpoint after processing a page.

        Args:
            context: Current pipeline context.
            page_index: Index of last successfully processed page.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_data = {
            "last_processed_page": page_index,
            "extractions": context.extractions,
            "format_spec": context.format_spec,
            "max_words": context.config.max_words,
        }

        # Save document state if available
        if context.document:
            checkpoint_data["document_state"] = context.document.to_dict()

        self.checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2))

    def load(self) -> Optional[Dict[str, Any]]:
        """Load checkpoint data.

        Returns:
            Checkpoint data dictionary or None if loading fails.
        """
        if not self.exists():
            return None

        try:
            return json.loads(self.checkpoint_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not load checkpoint: {e}")
            return None

    def restore_context(
        self,
        context: "PipelineContext",
        document_class: type,
    ) -> bool:
        """Restore context state from checkpoint.

        Args:
            context: Pipeline context to restore into.
            document_class: LiveDocument class for restoration.

        Returns:
            True if checkpoint was loaded successfully.
        """
        data = self.load()
        if not data:
            return False

        context.last_processed_page = data.get("last_processed_page", 0)
        context.extractions = data.get("extractions", [])
        context.format_spec = data.get("format_spec", context.format_spec)
        context.resumed = True

        # Update max_words from checkpoint
        if "max_words" in data:
            context.config.max_words = data["max_words"]

        # Restore document state
        doc_state = data.get("document_state")
        if doc_state and doc_state.get("sections"):
            context.document = document_class.from_dict(
                doc_state,
                context.format_spec,
                context.config.max_words,
            )

        return True

    def cleanup(self) -> None:
        """Remove checkpoint files after successful completion."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
            print("  Checkpoint cleared")

    def cleanup_images(self, image_dir: Path) -> None:
        """Remove temporary images directory.

        Args:
            image_dir: Directory containing converted page images.
        """
        if image_dir.exists():
            shutil.rmtree(image_dir)
            print("  Temporary images cleared")
