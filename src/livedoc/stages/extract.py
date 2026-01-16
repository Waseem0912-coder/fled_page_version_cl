"""Vision extraction stage."""

import json
from pathlib import Path
from typing import Any, Dict, List

from livedoc.core.stage import PipelineStage
from livedoc.core.context import PipelineContext
from livedoc.llm.client import LLMError


# Load prompt template
EXTRACTION_PROMPT = """Analyze this document page and extract structured information.

Return ONLY valid JSON with this exact structure:
{
  "events": [
    {
      "date": "YYYY-MM-DD or null if unknown",
      "type": "incident|decision|communication|action|other",
      "summary": "One sentence description",
      "actors": ["person or team names involved"]
    }
  ],
  "entities": ["Named systems, services, people, organizations"],
  "topics": ["Key themes: infrastructure, security, communication, etc"],
  "dates_mentioned": ["All dates found, any format"],
  "key_facts": ["Important standalone facts not tied to events"]
}

Rules:
- Extract ALL dates visible, even partial ones
- Preserve exact names and terminology
- One event per distinct occurrence
- If page is mostly blank or illegible, return empty arrays"""


class ExtractStage(PipelineStage):
    """Pipeline stage that extracts structured information from page images.

    Uses vision LLM to extract events, entities, topics, dates, and key facts
    from each page image.
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
        print("\n--- Stage: Extracting information from pages ---")

        if not context.image_paths:
            print("Warning: No images to extract from")
            return context

        # Keep existing extractions if resuming
        if context.last_processed_page == 0:
            context.extractions = []

        total_pages = len(context.image_paths)

        for idx, image_path in enumerate(context.image_paths, start=1):
            # Skip already processed pages
            if idx <= context.last_processed_page:
                continue

            print(f"  Extracting page {idx}/{total_pages}: {image_path.name}")

            extraction = self._extract_page(image_path, context)

            # Add metadata
            extraction["_source_image"] = image_path.name
            extraction["_page_index"] = idx

            # Validate and add
            if self._validate_extraction(extraction):
                context.extractions.append(extraction)
            else:
                print("    Warning: Invalid extraction structure, using empty fallback")
                context.extractions.append(self._empty_extraction(image_path.name, idx))

        if context.debug:
            self._save_debug_json(context)

        return context

    def _extract_page(
        self,
        image_path: Path,
        context: PipelineContext,
    ) -> Dict[str, Any]:
        """Extract structured information from a single page image.

        Args:
            image_path: Path to the page image.
            context: Pipeline context with LLM client.

        Returns:
            Dictionary with extracted information.
        """
        try:
            response = context.llm_client.chat(
                prompt=EXTRACTION_PROMPT,
                images=[image_path],
                json_mode=True,
            )
            return json.loads(response)

        except json.JSONDecodeError as e:
            print(f"    Warning: Failed to parse JSON from {image_path.name}: {e}")
            return self._empty_extraction(image_path.name)

        except LLMError as e:
            print(f"    Warning: LLM error for {image_path.name}: {e}")
            return self._empty_extraction(image_path.name)

        except Exception as e:
            print(f"    Warning: Unexpected error extracting {image_path.name}: {e}")
            return self._empty_extraction(image_path.name)

    def _empty_extraction(
        self,
        source_image: str = "",
        page_index: int = 0,
    ) -> Dict[str, Any]:
        """Return empty extraction structure for fallback.

        Args:
            source_image: Source image name.
            page_index: Page index.

        Returns:
            Empty extraction dictionary.
        """
        return {
            "events": [],
            "entities": [],
            "topics": [],
            "dates_mentioned": [],
            "key_facts": [],
            "_source_image": source_image,
            "_page_index": page_index,
        }

    def _validate_extraction(self, extraction: Dict[str, Any]) -> bool:
        """Validate that extraction has required fields.

        Args:
            extraction: Dictionary from extraction.

        Returns:
            True if extraction has valid structure.
        """
        required_fields = ["events", "entities", "topics", "dates_mentioned", "key_facts"]

        for field in required_fields:
            if field not in extraction:
                return False
            if not isinstance(extraction[field], list):
                return False

        # Validate event structure if events exist
        for event in extraction.get("events", []):
            if not isinstance(event, dict):
                return False
            if "summary" not in event:
                return False

        # Validate that string-list fields contain strings (not dicts)
        string_list_fields = ["entities", "topics", "dates_mentioned", "key_facts"]
        for field in string_list_fields:
            for item in extraction.get(field, []):
                if not isinstance(item, str):
                    # Try to convert dicts to strings
                    extraction[field] = self._normalize_string_list(extraction[field])
                    break

        return True

    def _normalize_string_list(self, items: List[Any]) -> List[str]:
        """Convert list items to strings if they are dicts or other types.

        Args:
            items: List that may contain non-string items.

        Returns:
            List with all items converted to strings.
        """
        result = []
        for item in items:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                # Try common keys that might contain the string value
                for key in ["text", "value", "name", "fact", "topic", "entity", "date"]:
                    if key in item and isinstance(item[key], str):
                        result.append(item[key])
                        break
                else:
                    # Fallback: convert dict to string representation
                    result.append(str(item))
            else:
                result.append(str(item))
        return result

    def _save_debug_json(self, context: PipelineContext) -> None:
        """Save extraction JSONs for debugging.

        Args:
            context: Pipeline context with extractions.
        """
        extraction_dir = context.get_extraction_dir()

        for extraction in context.extractions:
            filename = f"page_{extraction.get('_page_index', 0):03d}.json"
            filepath = extraction_dir / filename

            # Remove internal fields for clean output
            clean_extraction = {
                k: v for k, v in extraction.items() if not k.startswith("_")
            }
            filepath.write_text(json.dumps(clean_extraction, indent=2))

        print(f"  Debug JSONs saved to: {extraction_dir}")
