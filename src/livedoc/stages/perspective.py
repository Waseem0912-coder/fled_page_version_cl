"""Perspective rewriting stage."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from livedoc.core.stage import PipelineStage
from livedoc.core.context import PipelineContext
from livedoc.utils.parsing import parse_list_response


class PerspectiveStage(PipelineStage):
    """Pipeline stage for perspective-based rewriting.

    Supports two modes:
    - Mode A (section-level): Per-section goals with tailored prompts
    - Mode B (global): Single perspective applied to entire document
    """

    @property
    def name(self) -> str:
        return "perspective"

    def should_skip(self, context: PipelineContext) -> bool:
        """Skip if no perspective configuration provided."""
        return not (context.perspective_path or context.perspective_sections_path)

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Apply perspective rewriting based on configuration.

        Args:
            context: Pipeline context with perspective paths.

        Returns:
            Updated context (document rewritten in place).
        """
        if not context.document:
            return context

        if context.perspective_sections_path:
            # Mode A: Section-level perspective
            print(f"\n--- Applying section perspective: {context.perspective_sections_path.name} ---")
            self._rewrite_by_sections(context)
        elif context.perspective_path:
            # Mode B: Global perspective
            print(f"\n--- Applying global perspective: {context.perspective_path.name} ---")
            self._rewrite_global(context)

        return context

    def _rewrite_by_sections(self, context: PipelineContext) -> None:
        """Mode A: Apply per-section perspective goals.

        Args:
            context: Pipeline context.
        """
        config = yaml.safe_load(context.perspective_sections_path.read_text())
        meta = config.get("meta", {})
        section_configs = config.get("sections", {})

        for section_name, content_items in context.document.sections.items():
            if not content_items:
                continue

            section_config = section_configs.get(section_name, {})

            if section_config:
                # Generate tailored prompt for this section
                tailored_prompt = self._generate_section_prompt(
                    section_name,
                    section_config,
                    meta,
                    context,
                )

                # Rewrite with generated prompt
                rewritten = self._rewrite_section(
                    section_name,
                    content_items,
                    tailored_prompt,
                    section_config.get("max_words"),
                    section_config.get("preserve_format", False),
                    context,
                )
            else:
                # No specific config, apply only meta voice
                rewritten = self._rewrite_section_basic(
                    section_name, content_items, meta, context
                )

            context.document.sections[section_name] = rewritten

    def _generate_section_prompt(
        self,
        section_name: str,
        section_config: Dict[str, Any],
        meta: Dict[str, Any],
        context: PipelineContext,
    ) -> str:
        """Generate a tailored rewrite prompt for a section.

        Args:
            section_name: Name of the section.
            section_config: Section-specific configuration.
            meta: Global meta configuration.
            context: Pipeline context.

        Returns:
            Generated prompt string.
        """
        goal = section_config.get("goal", "Rewrite clearly")
        emphasize = section_config.get("emphasize", [])
        de_emphasize = section_config.get("de_emphasize", [])

        meta_prompt = f"""Create a rewrite prompt for the "{section_name}" section.

USER'S GOAL: {goal}

VOICE: {meta.get('voice', 'Professional')}
TERMINOLOGY: {meta.get('terminology', 'Standard')}

EMPHASIZE these aspects: {emphasize}
DE-EMPHASIZE these aspects: {de_emphasize}

Write a clear, direct prompt (3-5 sentences) that I'll use to rewrite the section.
The prompt should:
- Be specific about what to highlight
- Specify the tone/voice
- Give concrete guidance on what to change

Write only the prompt, nothing else."""

        try:
            return context.llm_client.chat(meta_prompt)
        except Exception as e:
            print(f"    Warning: Failed to generate section prompt: {e}")
            return f"Rewrite this section with emphasis on: {', '.join(emphasize)}"

    def _rewrite_section(
        self,
        section_name: str,
        content_items: List[str],
        tailored_prompt: str,
        max_words: Optional[int],
        preserve_format: bool,
        context: PipelineContext,
    ) -> List[str]:
        """Apply tailored prompt to rewrite a section.

        Args:
            section_name: Name of the section.
            content_items: Current content items.
            tailored_prompt: Generated rewrite prompt.
            max_words: Optional word limit.
            preserve_format: Whether to preserve structure.
            context: Pipeline context.

        Returns:
            Rewritten list of items.
        """
        content_text = "\n".join(f"- {item}" for item in content_items)
        word_constraint = f"\nKeep under {max_words} words." if max_words else ""
        format_note = "\nKeep the same structure/format." if preserve_format else ""

        rewrite_prompt = f"""{tailored_prompt}

SECTION CONTENT:
{content_text}

{word_constraint}{format_note}

CRITICAL: Keep all dates exactly as written. Keep all names exactly as written.

Rewrite the content. Output as a list with one item per line starting with dash:
- rewritten item 1
- rewritten item 2"""

        try:
            response = context.llm_client.chat(rewrite_prompt)
            result = parse_list_response(response)
            return result if result else content_items

        except Exception as e:
            print(f"    Warning: Failed to rewrite section {section_name}: {e}")
            return content_items

    def _rewrite_section_basic(
        self,
        section_name: str,
        content_items: List[str],
        meta: Dict[str, Any],
        context: PipelineContext,
    ) -> List[str]:
        """Apply basic rewrite with only meta voice settings.

        Args:
            section_name: Name of the section.
            content_items: Current content items.
            meta: Global meta configuration.
            context: Pipeline context.

        Returns:
            Rewritten list of items.
        """
        voice = meta.get("voice", "Professional")
        terminology = meta.get("terminology", "Standard")

        content_text = "\n".join(f"- {item}" for item in content_items)

        rewrite_prompt = f"""Rewrite this section content with the following style:

VOICE: {voice}
TERMINOLOGY: {terminology}

SECTION: {section_name}
{content_text}

CRITICAL: Keep all dates exactly as written. Keep all names exactly as written.

Output as a list with one item per line starting with dash:
- rewritten item 1
- rewritten item 2"""

        try:
            response = context.llm_client.chat(rewrite_prompt)
            result = parse_list_response(response)
            return result if result else content_items

        except Exception as e:
            print(f"    Warning: Failed basic rewrite for {section_name}: {e}")
            return content_items

    def _rewrite_global(self, context: PipelineContext) -> None:
        """Mode B: Apply single perspective to entire document.

        Args:
            context: Pipeline context.
        """
        perspective_config = context.perspective_path.read_text()

        # Render current document
        current_doc = context.document.to_markdown()

        # Check token budget - trim if needed
        if len(current_doc) > 6000:
            current_doc = self._trim_for_rewrite(current_doc, 5000)

        rewrite_prompt = f"""Rewrite this report from a specific perspective.

PERSPECTIVE GUIDE:
{perspective_config}

CURRENT REPORT:
{current_doc}

RULES:
- Keep ALL dates exactly as written
- Keep ALL entity/person names exactly as written
- Adjust emphasis and framing per the perspective guide
- Match the voice and terminology specified
- Stay within {context.config.max_words} words total

Write the complete rewritten report in markdown format."""

        try:
            response = context.llm_client.chat(rewrite_prompt)
            # Parse the rewritten document back into sections
            self._parse_markdown_to_sections(response, context)

        except Exception as e:
            print(f"    Warning: Global rewrite failed: {e}")

    def _parse_markdown_to_sections(
        self,
        markdown: str,
        context: PipelineContext,
    ) -> None:
        """Parse rewritten markdown back into document sections.

        Args:
            markdown: Rewritten markdown document.
            context: Pipeline context.
        """
        import re

        # Split by ## headers
        section_pattern = r'^##\s+(.+?)$'
        parts = re.split(section_pattern, markdown, flags=re.MULTILINE)

        current_section = None
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue

            # Check if this is a section header
            if i > 0 and i % 2 == 1:
                current_section = part
                if current_section in context.document.sections:
                    context.document.sections[current_section] = []
            elif current_section and current_section in context.document.sections:
                # Parse items from this section content
                items = parse_list_response(part)
                if items:
                    context.document.sections[current_section] = items

    def _trim_for_rewrite(self, doc: str, max_chars: int) -> str:
        """Trim document while keeping structure.

        Args:
            doc: Document to trim.
            max_chars: Maximum character count.

        Returns:
            Trimmed document.
        """
        if len(doc) <= max_chars:
            return doc

        # Keep first and last portions
        keep_start = int(max_chars * 0.6)
        keep_end = int(max_chars * 0.3)

        return doc[:keep_start] + "\n\n[... content trimmed ...]\n\n" + doc[-keep_end:]
