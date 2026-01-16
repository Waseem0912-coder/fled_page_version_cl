"""Parsing utilities for decisions and format specifications."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from livedoc.core.document import Decision


def parse_decision(response: str) -> Optional[Decision]:
    """Parse plain-text decision using regex.

    Expected format: "action: ADD, topic: server outage, section: Timeline"

    Args:
        response: Raw LLM response text.

    Returns:
        Decision object or None if parsing failed.
    """
    # Primary pattern
    pattern = r'action:\s*(ADD|UPDATE|SKIP)\s*,\s*topic:\s*([^,]+)\s*,\s*section:\s*(.+)'
    match = re.search(pattern, response, re.IGNORECASE)

    if match:
        return Decision(
            action=match.group(1).upper().strip(),
            topic=match.group(2).strip(),
            section=match.group(3).strip(),
        )

    # Fallback: try to extract just the action
    action_match = re.search(r'action:\s*(ADD|UPDATE|SKIP)', response, re.IGNORECASE)
    if action_match:
        return Decision(
            action=action_match.group(1).upper().strip(),
            topic="unknown",
            section="Timeline",  # Default section
        )

    return None


def parse_format_spec(format_path: Path, default_max_words: int = 1500) -> Dict[str, Any]:
    """Parse format.md to extract structure specification.

    Args:
        format_path: Path to format.md file.
        default_max_words: Default word limit if not specified.

    Returns:
        Dictionary with title, max_words, sections, section_order.
    """
    content = format_path.read_text()

    spec: Dict[str, Any] = {
        "title": "Report",
        "max_words": default_max_words,
        "sections": [],
        "section_order": [],
    }

    # Extract title from metadata
    title_match = re.search(r'-\s*title:\s*["\']?([^"\'\n]+)["\']?', content)
    if title_match:
        spec["title"] = title_match.group(1).strip()

    # Extract max_words from metadata
    words_match = re.search(r'-\s*max_words:\s*(\d+)', content)
    if words_match:
        spec["max_words"] = int(words_match.group(1))

    # Extract section names from ## headers under ## Structure
    structure_match = re.search(
        r'##\s+Structure\s*\n(.*?)(?=\n##\s+[^#]|\Z)',
        content,
        re.DOTALL,
    )
    if structure_match:
        structure_content = structure_match.group(1)
        # Find all ### headers within the structure section
        section_matches = re.findall(r'###\s+([^\n]+)', structure_content)
        spec["sections"] = [s.strip() for s in section_matches]
        spec["section_order"] = spec["sections"].copy()
    else:
        # Fallback: find all ### headers in the document
        section_matches = re.findall(r'###\s+([^\n]+)', content)
        if section_matches:
            spec["sections"] = [s.strip() for s in section_matches]
            spec["section_order"] = spec["sections"].copy()
        else:
            # Default sections
            spec["sections"] = [
                "Executive Summary",
                "Timeline",
                "Root Cause Analysis",
                "Impact Assessment",
                "Action Items",
            ]
            spec["section_order"] = spec["sections"].copy()

    return spec


def summarize_page_for_decision(page_data: Dict[str, Any]) -> str:
    """Create text summary of page JSON for decision prompt.

    Args:
        page_data: Extraction dict from a page.

    Returns:
        Compact text summary of the page content.
    """
    parts = []

    if page_data.get("events"):
        events = page_data["events"][:3]  # Limit to 3 events
        for e in events:
            date_str = e.get('date', 'no date')
            summary = e.get('summary', '')[:100]
            parts.append(f"- Event ({date_str}): {summary}")

    if page_data.get("topics"):
        topics = ", ".join(page_data["topics"][:5])
        parts.append(f"- Topics: {topics}")

    if page_data.get("key_facts"):
        facts = "; ".join(page_data["key_facts"][:3])
        parts.append(f"- Facts: {facts}")

    return "\n".join(parts) if parts else "No significant content extracted"


def generate_content_item(page_data: Dict[str, Any], topic: str) -> Optional[str]:
    """Generate a content item string from page data.

    Args:
        page_data: Extraction dict from a page.
        topic: Topic context for the item.

    Returns:
        Formatted content string or None if no content.
    """
    parts = []

    # Add events with dates
    for event in page_data.get("events", [])[:2]:
        date_str = f"({event.get('date')})" if event.get("date") else ""
        summary = event.get("summary", "")[:150]
        if summary:
            parts.append(f"{date_str} {summary}".strip())

    # Add key facts if no events
    if not parts:
        for fact in page_data.get("key_facts", [])[:2]:
            parts.append(fact[:150])

    if parts:
        return "; ".join(parts)

    return None


def parse_list_response(response: str, min_words: int = 0) -> List[str]:
    """Parse a list response from LLM output.

    Extracts lines starting with dashes as list items.

    Args:
        response: Raw LLM response text.
        min_words: Minimum words per item to include.

    Returns:
        List of extracted items.
    """
    items = []
    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("-"):
            item = line[1:].strip()
            if item and len(item.split()) >= min_words:
                items.append(item)
    return items
