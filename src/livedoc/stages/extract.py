"""Unified vision extraction stage - detects content types and extracts in one call."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from livedoc.core.stage import PipelineStage
from livedoc.core.context import PipelineContext
from livedoc.llm.client import LLMError


# Unified extraction prompt - detects content types AND extracts in one call
UNIFIED_EXTRACTION_PROMPT = """Analyze this document page. First identify what content types exist, then extract each appropriately.

{context_hint}

Return JSON:
{{
  "content_types": ["table", "chart", "graph", "image", "paragraph"],

  "tables": [{{
    "headers": ["col1", "col2"],
    "rows": [["val1", "val2"]],
    "summary": "What this table shows",
    "importance": 1-3
  }}],

  "visuals": [{{
    "type": "chart|graph|image|diagram",
    "description": "What it shows",
    "data_points": ["key values/labels visible"],
    "trend": "increasing|decreasing|stable|comparison|n/a",
    "importance": 1-3
  }}],

  "events": [{{
    "date": "YYYY-MM-DD or null",
    "type": "incident|decision|action|other",
    "summary": "<30 words",
    "actors": ["names"],
    "importance": 1-3
  }}],

  "entities": ["names, systems, orgs"],
  "dates": ["all dates found"],
  "facts": [{{"text": "<25 words", "importance": 1-3}}],

  "continues_previous": false,
  "continues_next": false
}}

RULES:
- List ALL content types present on the page
- For TABLES: Extract headers and key rows (max 10 rows)
- For CHARTS/GRAPHS: Describe trend, extract visible data points
- For IMAGES/DIAGRAMS: Describe what's shown, extract any labels
- For PARAGRAPHS: Extract events with dates, actors, importance
- Importance: 3=critical (dates, decisions), 2=high, 1=supporting
- Preserve exact names, dates, numbers
- Empty arrays if content type not present
- ONLY extract information EXPLICITLY visible - never infer or assume"""

# Context hint for cross-page continuity
CONTEXT_HINT_TEMPLATE = """Previous page context: Topics: {topics}. Key actors: {actors}.
Check if this page continues from previous."""


class ExtractStage(PipelineStage):
    """Pipeline stage that extracts structured information from page images.

    Uses unified detection + extraction approach:
    1. Detects content types on the page (tables, charts, graphs, images, paragraphs)
    2. Extracts each content type using appropriate strategy
    3. Adds importance scoring for smart compression
    4. Maintains cross-page continuity context
    """

    @property
    def name(self) -> str:
        return "extract"

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Extract information from all page images.

        Args:
            context: Pipeline context with image_paths.

        Returns:
            Updated context with extractions populated.
        """
        print("\n--- Stage: Extracting (unified detect + extract) ---")

        if not context.image_paths:
            print("Warning: No images to extract from")
            return context

        # Keep existing extractions if resuming
        if context.last_processed_page == 0:
            context.extractions = []

        total_pages = len(context.image_paths)
        prev_extraction: Optional[Dict[str, Any]] = None

        for idx, image_path in enumerate(context.image_paths, start=1):
            # Skip already processed pages
            if idx <= context.last_processed_page:
                # Track previous extraction for context
                if context.extractions and idx == context.last_processed_page:
                    prev_extraction = context.extractions[-1]
                continue

            print(f"  Page {idx}/{total_pages}: {image_path.name}")

            # Build context hint from previous page
            context_hint = ""
            if prev_extraction:
                context_hint = self._build_context_hint(prev_extraction)

            # Single unified extraction call
            extraction = self._extract_unified(image_path, context_hint, context)

            # Add metadata
            extraction["_page_index"] = idx
            extraction["_source_image"] = image_path.name

            # Log what was detected
            types = extraction.get("content_types", [])
            print(f"    Detected: {', '.join(types) if types else 'text only'}")

            # Validate and normalize
            extraction = self._normalize_extraction(extraction)
            context.extractions.append(extraction)
            prev_extraction = extraction

        if context.debug:
            self._save_debug_json(context)

        return context

    def _build_context_hint(self, prev_extraction: Dict[str, Any]) -> str:
        """Build context hint from previous page extraction.

        Args:
            prev_extraction: Previous page's extraction dict.

        Returns:
            Context hint string or empty if not applicable.
        """
        # Only provide context if previous page continues to next
        if not prev_extraction.get("continues_next", False):
            return ""

        # Extract topics - handle both old format (topics) and new (content_types)
        topics_list = prev_extraction.get("topics", [])
        if not topics_list:
            # Derive topics from content types
            topics_list = prev_extraction.get("content_types", [])
        topics = ", ".join(topics_list[:3]) if topics_list else "none"

        # Extract actors from events
        actors = self._get_actors_from_extraction(prev_extraction)[:3]
        actors_str = ", ".join(actors) if actors else "none"

        return CONTEXT_HINT_TEMPLATE.format(topics=topics, actors=actors_str)

    def _get_actors_from_extraction(self, extraction: Dict[str, Any]) -> List[str]:
        """Extract unique actor names from extraction.

        Args:
            extraction: Page extraction dict.

        Returns:
            List of unique actor names.
        """
        actors = set()

        # From events
        for event in extraction.get("events", []):
            if isinstance(event, dict):
                for actor in event.get("actors", []):
                    if actor:
                        actors.add(str(actor))

        # From entities (as fallback)
        for entity in extraction.get("entities", []):
            if entity:
                actors.add(str(entity))

        return list(actors)

    def _extract_unified(
        self,
        image_path: Path,
        context_hint: str,
        context: PipelineContext,
    ) -> Dict[str, Any]:
        """Extract structured information using unified prompt.

        Args:
            image_path: Path to the page image.
            context_hint: Context from previous page (or empty).
            context: Pipeline context with LLM client.

        Returns:
            Dictionary with extracted information.
        """
        prompt = UNIFIED_EXTRACTION_PROMPT.format(context_hint=context_hint)

        try:
            response = context.llm_client.chat(
                prompt=prompt,
                images=[image_path],
                json_mode=True,
            )
            return json.loads(response)

        except json.JSONDecodeError as e:
            print(f"    Warning: Failed to parse JSON: {e}")
            return self._empty_extraction()

        except LLMError as e:
            print(f"    Warning: LLM error: {e}")
            return self._empty_extraction()

        except Exception as e:
            print(f"    Warning: Unexpected error: {e}")
            return self._empty_extraction()

    def _empty_extraction(self) -> Dict[str, Any]:
        """Return empty extraction structure for fallback.

        Returns:
            Empty extraction dictionary with all expected fields.
        """
        return {
            "content_types": [],
            "tables": [],
            "visuals": [],
            "events": [],
            "entities": [],
            "dates": [],
            "facts": [],
            "continues_previous": False,
            "continues_next": False,
        }

    def _normalize_extraction(self, extraction: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and validate extraction structure.

        Ensures all expected fields exist and have correct types.
        Handles backward compatibility with old format.

        Args:
            extraction: Raw extraction from LLM.

        Returns:
            Normalized extraction dictionary.
        """
        # Ensure all fields exist with defaults
        defaults = self._empty_extraction()
        for key, default_value in defaults.items():
            if key not in extraction:
                extraction[key] = default_value

        # Normalize content_types to list of strings
        if not isinstance(extraction.get("content_types"), list):
            extraction["content_types"] = []

        # Normalize tables
        extraction["tables"] = self._normalize_tables(extraction.get("tables", []))

        # Normalize visuals
        extraction["visuals"] = self._normalize_visuals(extraction.get("visuals", []))

        # Normalize events
        extraction["events"] = self._normalize_events(extraction.get("events", []))

        # Normalize facts (can be strings or dicts)
        extraction["facts"] = self._normalize_facts(extraction.get("facts", []))

        # Normalize string lists
        for field in ["entities", "dates"]:
            extraction[field] = self._normalize_string_list(extraction.get(field, []))

        # Handle backward compatibility: dates_mentioned -> dates
        if "dates_mentioned" in extraction and extraction["dates_mentioned"]:
            extraction["dates"].extend(
                self._normalize_string_list(extraction["dates_mentioned"])
            )

        # Handle backward compatibility: key_facts -> facts
        if "key_facts" in extraction and extraction["key_facts"]:
            old_facts = extraction["key_facts"]
            for fact in old_facts:
                if isinstance(fact, str):
                    extraction["facts"].append({"text": fact, "importance": 1})
                elif isinstance(fact, dict):
                    extraction["facts"].append(fact)

        return extraction

    def _normalize_tables(self, tables: Any) -> List[Dict[str, Any]]:
        """Normalize table data.

        Args:
            tables: Raw tables data.

        Returns:
            List of normalized table dicts.
        """
        if not isinstance(tables, list):
            return []

        normalized = []
        for table in tables:
            if not isinstance(table, dict):
                continue

            normalized.append({
                "headers": self._normalize_string_list(table.get("headers", [])),
                "rows": self._normalize_table_rows(table.get("rows", [])),
                "summary": str(table.get("summary", "")),
                "importance": self._normalize_importance(table.get("importance", 2)),
            })

        return normalized

    def _normalize_table_rows(self, rows: Any) -> List[List[str]]:
        """Normalize table rows.

        Args:
            rows: Raw rows data.

        Returns:
            List of row lists.
        """
        if not isinstance(rows, list):
            return []

        normalized = []
        for row in rows[:10]:  # Limit to 10 rows
            if isinstance(row, list):
                normalized.append([str(cell) for cell in row])
            elif isinstance(row, dict):
                # Handle dict rows by extracting values
                normalized.append([str(v) for v in row.values()])

        return normalized

    def _normalize_visuals(self, visuals: Any) -> List[Dict[str, Any]]:
        """Normalize visual data.

        Args:
            visuals: Raw visuals data.

        Returns:
            List of normalized visual dicts.
        """
        if not isinstance(visuals, list):
            return []

        normalized = []
        for visual in visuals:
            if not isinstance(visual, dict):
                continue

            normalized.append({
                "type": str(visual.get("type", visual.get("visual_type", "image"))),
                "description": str(visual.get("description", "")),
                "data_points": self._normalize_string_list(visual.get("data_points", [])),
                "trend": str(visual.get("trend", "n/a")),
                "importance": self._normalize_importance(visual.get("importance", 2)),
            })

        return normalized

    def _normalize_events(self, events: Any) -> List[Dict[str, Any]]:
        """Normalize event data.

        Args:
            events: Raw events data.

        Returns:
            List of normalized event dicts.
        """
        if not isinstance(events, list):
            return []

        normalized = []
        for event in events:
            if not isinstance(event, dict):
                continue

            # Skip events without summary
            summary = event.get("summary", "")
            if not summary:
                continue

            normalized.append({
                "date": event.get("date"),
                "type": str(event.get("type", "other")),
                "summary": str(summary),
                "actors": self._normalize_string_list(event.get("actors", [])),
                "importance": self._normalize_importance(event.get("importance", 2)),
            })

        return normalized

    def _normalize_facts(self, facts: Any) -> List[Dict[str, Any]]:
        """Normalize facts data.

        Args:
            facts: Raw facts data (can be strings or dicts).

        Returns:
            List of normalized fact dicts with text and importance.
        """
        if not isinstance(facts, list):
            return []

        normalized = []
        for fact in facts:
            if isinstance(fact, str):
                normalized.append({"text": fact, "importance": 1})
            elif isinstance(fact, dict):
                text = fact.get("text", fact.get("fact", ""))
                if text:
                    normalized.append({
                        "text": str(text),
                        "importance": self._normalize_importance(fact.get("importance", 1)),
                    })

        return normalized

    def _normalize_string_list(self, items: Any) -> List[str]:
        """Convert list items to strings.

        Args:
            items: List that may contain non-string items.

        Returns:
            List with all items as strings.
        """
        if not isinstance(items, list):
            return []

        result = []
        for item in items:
            if isinstance(item, str):
                if item:
                    result.append(item)
            elif isinstance(item, dict):
                # Try common keys
                for key in ["text", "value", "name", "fact", "topic", "entity", "date"]:
                    if key in item and isinstance(item[key], str):
                        result.append(item[key])
                        break
                else:
                    result.append(str(item))
            elif item is not None:
                result.append(str(item))

        return result

    def _normalize_importance(self, value: Any) -> int:
        """Normalize importance value to 1-3 range.

        Args:
            value: Raw importance value.

        Returns:
            Integer 1-3.
        """
        try:
            importance = int(value)
            return max(1, min(3, importance))
        except (ValueError, TypeError):
            return 2

    def _save_debug_json(self, context: PipelineContext) -> None:
        """Save extraction JSONs for debugging.

        Args:
            context: Pipeline context with extractions.
        """
        extraction_dir = context.get_extraction_dir()

        for extraction in context.extractions:
            page_idx = extraction.get("_page_index", 0)
            filename = f"page_{page_idx:03d}.json"
            filepath = extraction_dir / filename

            # Remove internal fields for clean output
            clean_extraction = {
                k: v for k, v in extraction.items() if not k.startswith("_")
            }
            filepath.write_text(json.dumps(clean_extraction, indent=2))

        print(f"  Debug JSONs saved to: {extraction_dir}")
