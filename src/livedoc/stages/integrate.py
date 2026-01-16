"""Integration stage - builds LiveDocument from extractions."""

from typing import Any, Dict, List, Optional

from livedoc.core.stage import PipelineStage
from livedoc.core.context import PipelineContext
from livedoc.core.document import LiveDocument
from livedoc.utils.parsing import (
    parse_decision,
    summarize_page_for_decision,
    generate_content_item,
)
from livedoc.utils.checkpoint import CheckpointManager


DECISION_PROMPT_TEMPLATE = """New information extracted from document page:
---
{page_summary}
---

Current report sections:
{compact_state}

Available sections: {sections}

What should I do with this new information?
Reply with EXACTLY this format on one line:
action: [ADD/UPDATE/SKIP], topic: [brief topic], section: [section name]

- ADD = new information not in report
- UPDATE = extends or corrects existing entry
- SKIP = redundant or not relevant"""


class IntegrateStage(PipelineStage):
    """Pipeline stage that builds a LiveDocument from page extractions.

    Processes each extraction and decides whether to ADD, UPDATE, or SKIP
    content based on LLM decisions. Triggers compression when needed.
    """

    @property
    def name(self) -> str:
        return "integrate"

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Build LiveDocument from extractions.

        Args:
            context: Pipeline context with extractions.

        Returns:
            Updated context with document populated.
        """
        print("\n--- Stage: Building LiveDocument ---")

        if not context.extractions:
            print("Warning: No extractions to integrate")
            return context

        # Initialize document if not resuming
        if not context.document:
            context.document = LiveDocument(
                format_spec=context.format_spec,
                max_words=context.config.max_words,
            )

        checkpoint_manager = CheckpointManager(context.output_dir)

        for idx, extraction in enumerate(context.extractions, start=1):
            page_index = extraction.get("_page_index", idx)

            # Skip already processed pages
            if page_index <= context.last_processed_page:
                continue

            # Skip empty extractions
            if not self._has_content(extraction):
                print(f"  Page {page_index}: SKIP (no significant content)")
                continue

            action = self._process_page(extraction, context)
            print(
                f"  Page {page_index}: {action} "
                f"(words: {context.document.current_word_count()})"
            )

            # Check if compression needed
            if context.document.needs_compression(context.config.compression_threshold):
                self._compress_document(context)

            # Save checkpoint after each page
            context.last_processed_page = page_index
            checkpoint_manager.save(context, page_index)

        return context

    def _has_content(self, extraction: Dict[str, Any]) -> bool:
        """Check if extraction has any significant content.

        Args:
            extraction: Page extraction dict.

        Returns:
            True if extraction has meaningful content.
        """
        return any([
            extraction.get("events"),
            extraction.get("key_facts"),
            extraction.get("topics"),
        ])

    def _process_page(
        self,
        extraction: Dict[str, Any],
        context: PipelineContext,
    ) -> str:
        """Process one page extraction and return action taken.

        Args:
            extraction: Page extraction dict.
            context: Pipeline context.

        Returns:
            Action taken: ADD, UPDATE, or SKIP.
        """
        # Create compact summary for decision
        page_summary = summarize_page_for_decision(extraction)

        # Check token budget - truncate if needed
        if len(page_summary) + len(context.document.get_compact_state()) > 2000:
            page_summary = page_summary[:1500] + "..."

        decision_prompt = DECISION_PROMPT_TEMPLATE.format(
            page_summary=page_summary,
            compact_state=context.document.get_compact_state(),
            sections=list(context.document.sections.keys()),
        )

        try:
            response = context.llm_client.chat(decision_prompt)
            decision = parse_decision(response)

            if decision is None:
                print(f"    Warning: Could not parse decision, skipping. Response: {response[:100]}")
                return "SKIP"

            # Validate section exists
            if decision.section not in context.document.sections:
                decision.section = context.document.find_closest_section(decision.section)

            # Apply the decision
            if decision.action == "ADD":
                self._add_content(extraction, decision.section, decision.topic, context)
            elif decision.action == "UPDATE":
                self._update_content(extraction, decision.section, decision.topic, context)
            # SKIP does nothing

            # Track protected items from this page
            context.document.track_protected_items(extraction)

            return decision.action

        except Exception as e:
            print(f"    Warning: Error processing page: {e}")
            return "SKIP"

    def _add_content(
        self,
        extraction: Dict[str, Any],
        section: str,
        topic: str,
        context: PipelineContext,
    ) -> None:
        """Add new content to a section.

        Args:
            extraction: Page extraction dict.
            section: Target section name.
            topic: Brief topic description.
            context: Pipeline context.
        """
        content_item = generate_content_item(extraction, topic)
        if content_item:
            context.document.add_content(section, content_item)

    def _update_content(
        self,
        extraction: Dict[str, Any],
        section: str,
        topic: str,
        context: PipelineContext,
    ) -> None:
        """Update existing content in a section.

        Args:
            extraction: Page extraction dict.
            section: Target section name.
            topic: Topic to match.
            context: Pipeline context.
        """
        if not context.document.sections.get(section):
            # No existing content, treat as ADD
            self._add_content(extraction, section, topic, context)
            return

        # Find most relevant existing item to update
        best_idx = context.document.find_related_item(section, topic)

        if best_idx is not None:
            # Merge new information with existing item
            existing = context.document.sections[section][best_idx]
            new_content = generate_content_item(extraction, topic)
            if new_content:
                merged = f"{existing}. Additionally: {new_content}"
                context.document.update_content(section, best_idx, merged)
        else:
            # No related item found, add as new
            self._add_content(extraction, section, topic, context)

    def _compress_document(self, context: PipelineContext) -> None:
        """Trigger compression with escalating strategies.

        Args:
            context: Pipeline context with document.
        """
        # Import here to avoid circular dependency
        from livedoc.stages.compress import CompressStage

        compress_stage = CompressStage()
        compress_stage.execute(context)
