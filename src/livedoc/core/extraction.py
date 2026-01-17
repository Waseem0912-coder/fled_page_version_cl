"""Data structures for page extraction with multi-content type support."""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ContentType(Enum):
    """Types of content detected on a page."""
    TABLE = "table"
    CHART = "chart"
    GRAPH = "graph"
    IMAGE = "image"
    PARAGRAPH = "paragraph"


class ImportanceLevel(Enum):
    """Item importance for compression prioritization."""
    CRITICAL = 3  # Dates, key decisions - must survive
    HIGH = 2      # Important context
    MEDIUM = 1    # Supporting details


@dataclass
class TableData:
    """Extracted table content."""
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    summary: str = ""
    importance: int = 2


@dataclass
class VisualData:
    """Extracted chart/graph/image content."""
    visual_type: str = ""  # chart, graph, image, diagram
    description: str = ""
    data_points: List[str] = field(default_factory=list)  # Key values shown
    trend: str = ""  # For charts/graphs: "increasing", "decreasing", etc.
    importance: int = 2


@dataclass
class ExtractedEvent:
    """Event from paragraphs."""
    date: Optional[str] = None
    type: str = "other"  # incident|decision|action|other
    summary: str = ""
    actors: List[str] = field(default_factory=list)
    importance: int = 2


@dataclass
class PageExtraction:
    """Complete extraction with all content types."""
    page_index: int
    source_image: str

    # Detected content types on this page
    content_types: List[str] = field(default_factory=list)

    # Type-specific extractions
    tables: List[TableData] = field(default_factory=list)
    visuals: List[VisualData] = field(default_factory=list)
    events: List[ExtractedEvent] = field(default_factory=list)

    # Common extractions
    entities: List[str] = field(default_factory=list)
    dates_mentioned: List[str] = field(default_factory=list)
    key_facts: List[dict] = field(default_factory=list)  # {text, importance}

    # Cross-page continuity
    continues_from_previous: bool = False
    continues_to_next: bool = False
