"""LiveDoc - Document Processing Pipeline.

A modular pipeline for converting PDFs to structured reports using vision LLMs.
"""

__version__ = "0.1.0"

from livedoc.core.pipeline import Pipeline
from livedoc.core.context import PipelineContext
from livedoc.core.stage import PipelineStage
from livedoc.core.document import LiveDocument
from livedoc.config.settings import PipelineConfig

__all__ = [
    "Pipeline",
    "PipelineContext",
    "PipelineStage",
    "LiveDocument",
    "PipelineConfig",
]
