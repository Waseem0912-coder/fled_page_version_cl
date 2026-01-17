"""Pipeline stages for document processing."""

from livedoc.stages.convert import ConvertStage
from livedoc.stages.extract import ExtractStage
from livedoc.stages.integrate import IntegrateStage
from livedoc.stages.compress import CompressStage
from livedoc.stages.perspective import PerspectiveStage
from livedoc.stages.finalize import FinalizeStage

__all__ = [
    "ConvertStage",
    "ExtractStage",
    "IntegrateStage",
    "CompressStage",
    "PerspectiveStage",
    "FinalizeStage",
]
