"""LiveDocument state management.

Contains the document state that is built incrementally from page extractions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class Decision:
    """Represents an LLM decision about how to handle new content.

    Attributes:
        action: The action to take (ADD, UPDATE, SKIP).
        topic: Brief description of what the content is about.
        section: Target section name for the content.
    """

    action: str  # ADD, UPDATE, SKIP
    topic: str
    section: str


class LiveDocument:
    """Document state that is built incrementally from page extractions.

    Maintains sections with content items and tracks protected items
    (dates, entities, topics) that must survive compression.

    Attributes:
        max_words: Maximum word count for the final document.
        format_spec: Parsed format specification with sections.
        sections: Content organized by section name.
        tracked_dates: Dates that must survive compression.
        tracked_entities: Entity names that must survive compression.
        tracked_topics: Topic keywords that must survive compression.
    """

    def __init__(self, format_spec: Dict[str, Any], max_words: int):
        """Initialize the LiveDocument.

        Args:
            format_spec: Parsed format specification with sections.
            max_words: Maximum word count for final document.
        """
        self.max_words = max_words
        self.format_spec = format_spec
        self.sections: Dict[str, List[str]] = {
            s: [] for s in format_spec.get("sections", [])
        }
        self.tracked_dates: Set[str] = set()
        self.tracked_entities: Set[str] = set()
        self.tracked_topics: Set[str] = set()

    def current_word_count(self) -> int:
        """Calculate total words in the document.

        Returns:
            Total word count across all sections.
        """
        return sum(
            len(" ".join(items).split())
            for items in self.sections.values()
        )

    def needs_compression(self, threshold: float = 0.85) -> bool:
        """Check if document is over the compression threshold.

        Args:
            threshold: Percentage of word budget that triggers compression.

        Returns:
            True if word count exceeds threshold * max_words.
        """
        return self.current_word_count() > (self.max_words * threshold)

    def add_content(self, section: str, content: str) -> None:
        """Add new content to a section.

        Args:
            section: Target section name.
            content: Content item to add.
        """
        if section in self.sections:
            self.sections[section].append(content)

    def update_content(self, section: str, index: int, content: str) -> None:
        """Update existing content at a specific index.

        Args:
            section: Target section name.
            index: Index of the item to update.
            content: New content to replace with.
        """
        if section in self.sections and 0 <= index < len(self.sections[section]):
            self.sections[section][index] = content

    def track_protected_items(self, page_data: Dict[str, Any]) -> None:
        """Track dates and entities that must survive compression.

        Args:
            page_data: Extraction dict from a page.
        """
        for event in page_data.get("events", []):
            if event.get("date"):
                self.tracked_dates.add(event["date"])
            for actor in event.get("actors", []):
                self.tracked_entities.add(actor)

        for entity in page_data.get("entities", []):
            self.tracked_entities.add(entity)

        for date in page_data.get("dates_mentioned", []):
            self.tracked_dates.add(date)

        for topic in page_data.get("topics", []):
            self.tracked_topics.add(topic)

    def find_related_item(self, section: str, topic: str) -> Optional[int]:
        """Find index of most related item in a section.

        Uses word overlap to find the best matching item.

        Args:
            section: Section to search.
            topic: Topic to match.

        Returns:
            Index of best matching item or None if no match found.
        """
        topic_words = set(topic.lower().split())
        items = self.sections.get(section, [])

        best_score = 0
        best_idx = None

        for idx, item in enumerate(items):
            item_words = set(item.lower().split())
            overlap = len(topic_words & item_words)
            if overlap > best_score:
                best_score = overlap
                best_idx = idx

        # Only return if there's meaningful overlap
        return best_idx if best_score >= 1 else None

    def find_closest_section(self, section_name: str) -> str:
        """Find closest matching section name.

        Args:
            section_name: Potentially misspelled section name.

        Returns:
            Best matching section name.
        """
        section_lower = section_name.lower()
        for section in self.sections.keys():
            if section.lower() in section_lower or section_lower in section.lower():
                return section

        # Default to first section or Timeline
        if "Timeline" in self.sections:
            return "Timeline"
        return list(self.sections.keys())[0] if self.sections else section_name

    def get_compact_state(self) -> str:
        """Return minimal state representation for decision prompt.

        Returns:
            Compact string representation of current document state.
        """
        lines = []
        for section, items in self.sections.items():
            if items:
                # Only show first line of each item to save tokens
                previews = [item.split('.')[0][:80] for item in items[:5]]
                lines.append(f"[{section}]: {len(items)} items - {', '.join(previews)}")
        return "\n".join(lines) if lines else "(empty document)"

    def to_markdown(self) -> str:
        """Render the document as markdown.

        Returns:
            Complete markdown document string.
        """
        lines = [f"# {self.format_spec.get('title', 'Report')}\n"]

        section_order = self.format_spec.get("section_order", list(self.sections.keys()))

        for section_name in section_order:
            if section_name in self.sections and self.sections[section_name]:
                lines.append(f"## {section_name}\n")
                for item in self.sections[section_name]:
                    lines.append(f"- {item}")
                lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize document state to dictionary for checkpointing.

        Returns:
            Dictionary representation of document state.
        """
        return {
            "sections": self.sections,
            "tracked_dates": list(self.tracked_dates),
            "tracked_entities": list(self.tracked_entities),
            "tracked_topics": list(self.tracked_topics),
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        format_spec: Dict[str, Any],
        max_words: int,
    ) -> "LiveDocument":
        """Restore document state from dictionary.

        Args:
            data: Serialized document state.
            format_spec: Format specification.
            max_words: Maximum word count.

        Returns:
            Restored LiveDocument instance.
        """
        doc = cls(format_spec, max_words)
        doc.sections = data.get("sections", doc.sections)
        doc.tracked_dates = set(data.get("tracked_dates", []))
        doc.tracked_entities = set(data.get("tracked_entities", []))
        doc.tracked_topics = set(data.get("tracked_topics", []))
        return doc
