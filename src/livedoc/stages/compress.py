"""Compression stage - intelligently compresses content while preserving critical info."""

from typing import Any, Dict, List, Set

from livedoc.core.stage import PipelineStage
from livedoc.core.context import PipelineContext
from livedoc.config.settings import CompressionConfig
from livedoc.utils.parsing import parse_list_response


COMPRESSION_PROMPT_TEMPLATE = """Compress these report items while keeping all protected terms.

ITEMS TO COMPRESS:
{items}

{protected_terms}

COMPRESSION RULES:
1. NEVER change or remove dates - copy exactly as written
2. NEVER change entity/person names - copy exactly
3. Merge items about the same event into one
4. Remove filler words (very, really, basically, etc.)
5. Keep technical terms and error codes
6. Each output item should be 8-25 words

Write compressed items as a simple list, one per line starting with dash:
- compressed item 1
- compressed item 2"""


class CompressStage(PipelineStage):
    """Pipeline stage that compresses content while preserving protected items.

    Uses multi-stage compression with fallback to item dropping.
    Protected items (dates, entities, topics) are preserved and restored if lost.
    """

    @property
    def name(self) -> str:
        return "compress"

    def should_skip(self, context: PipelineContext) -> bool:
        """Skip if document doesn't need compression."""
        if not context.document:
            return True
        return not context.document.needs_compression(context.config.compression_threshold)

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute compression with escalating strategies.

        Args:
            context: Pipeline context with document.

        Returns:
            Updated context with compressed document.
        """
        if not context.document:
            return context

        initial_count = context.document.current_word_count()
        print(f"Compressing... (current: {initial_count} words, target: {context.config.max_words})")

        # Attempt 1: Normal compression (30% reduction)
        self._apply_compression(context, target_reduction=0.30)

        if context.document.current_word_count() <= context.config.max_words:
            print(f"After compression: {context.document.current_word_count()} words")
            return context

        # Attempt 2: Aggressive compression (50% reduction)
        print(f"  Still over limit ({context.document.current_word_count()} words), "
              "trying aggressive compression...")
        self._apply_compression(context, target_reduction=0.50)

        if context.document.current_word_count() <= context.config.max_words:
            print(f"After aggressive compression: {context.document.current_word_count()} words")
            return context

        # Attempt 3: Drop oldest items without protected content
        print(f"  Still over limit ({context.document.current_word_count()} words), "
              "dropping oldest items...")
        self._drop_oldest_items(context)

        final_count = context.document.current_word_count()
        if final_count > context.config.max_words:
            print(f"WARNING: Could not reduce below word limit. Final: {final_count} words")
        else:
            print(f"After dropping items: {final_count} words")

        return context

    def _apply_compression(
        self,
        context: PipelineContext,
        target_reduction: float,
    ) -> None:
        """Apply compression with specified reduction target.

        Args:
            context: Pipeline context.
            target_reduction: Target reduction ratio (0.30 = 30% reduction).
        """
        config = CompressionConfig(target_reduction=target_reduction)

        for section_name, items in context.document.sections.items():
            if len(items) > 2:
                compressed = self._compress_section(
                    items=items,
                    protected_dates=context.document.tracked_dates,
                    protected_entities=context.document.tracked_entities,
                    protected_topics=context.document.tracked_topics,
                    context=context,
                    config=config,
                )
                context.document.sections[section_name] = compressed

    def _compress_section(
        self,
        items: List[str],
        protected_dates: Set[str],
        protected_entities: Set[str],
        protected_topics: Set[str],
        context: PipelineContext,
        config: CompressionConfig,
    ) -> List[str]:
        """Compress a section while preserving protected content.

        Args:
            items: List of content items.
            protected_dates: Dates that must survive.
            protected_entities: Entity names that must survive.
            protected_topics: Topic keywords that must survive.
            context: Pipeline context.
            config: Compression configuration.

        Returns:
            Compressed list of items.
        """
        if len(items) <= 2:
            return items

        # Build index of which items contain which protected terms
        date_sources = self._find_protected_sources(items, protected_dates)
        entity_sources = self._find_protected_sources(items, protected_entities)

        # Build protected terms list for prompt
        protected_terms = self._build_protected_list(
            protected_dates, protected_entities, protected_topics
        )

        # Process in chunks
        compressed_items = []
        for i in range(0, len(items), config.chunk_size):
            chunk = items[i:i + config.chunk_size]

            # Check if chunk even needs compression
            # Ensure all items are strings for word counting
            chunk_words = sum(
                len((str(item) if not isinstance(item, str) else item).split())
                for item in chunk
            )
            if chunk_words < 50:
                compressed_items.extend(chunk)
                continue

            compressed_chunk = self._compress_chunk(
                chunk, protected_terms, context, config
            )
            compressed_items.extend(compressed_chunk)

        # Validation and restoration pass
        compressed_items = self._validate_and_restore(
            compressed_items,
            items,
            protected_dates,
            protected_entities,
            date_sources,
            entity_sources,
        )

        return compressed_items

    def _find_protected_sources(
        self,
        items: List[str],
        protected_terms: Set[str],
    ) -> Dict[str, str]:
        """Find which original items contain each protected term.

        Args:
            items: Original items list.
            protected_terms: Terms to find.

        Returns:
            Dict mapping protected term to original item containing it.
        """
        sources = {}
        for term in protected_terms:
            term_lower = term.lower()
            for item in items:
                # Ensure item is a string
                item_str = str(item) if not isinstance(item, str) else item
                if term_lower in item_str.lower():
                    sources[term] = item_str
                    break
        return sources

    def _build_protected_list(
        self,
        dates: Set[str],
        entities: Set[str],
        topics: Set[str],
    ) -> str:
        """Create compact protected items reference for prompt.

        Args:
            dates: Protected dates.
            entities: Protected entities.
            topics: Protected topics.

        Returns:
            Formatted string for prompt.
        """
        parts = []
        if dates:
            parts.append(f"DATES (keep exactly): {', '.join(sorted(dates)[:10])}")
        if entities:
            parts.append(f"NAMES (keep exactly): {', '.join(sorted(entities)[:15])}")
        if topics:
            parts.append(f"TOPICS (keep keywords): {', '.join(sorted(topics)[:10])}")
        return "\n".join(parts)

    def _compress_chunk(
        self,
        chunk: List[str],
        protected_terms: str,
        context: PipelineContext,
        config: CompressionConfig,
    ) -> List[str]:
        """Compress a small chunk of items.

        Args:
            chunk: Items to compress.
            protected_terms: Protected terms string.
            context: Pipeline context.
            config: Compression configuration.

        Returns:
            Compressed items.
        """
        # Ensure all items are strings
        string_chunk = [str(item) if not isinstance(item, str) else item for item in chunk]
        chunk_text = "\n".join(f"- {item}" for item in string_chunk)

        # Estimate if we're within token budget
        prompt_estimate = len(chunk_text) + len(protected_terms) + 600
        if prompt_estimate > config.max_prompt_tokens * 4:  # chars to tokens
            # Chunk too big, split further
            mid = len(chunk) // 2
            left = self._compress_chunk(chunk[:mid], protected_terms, context, config)
            right = self._compress_chunk(chunk[mid:], protected_terms, context, config)
            return left + right

        compress_prompt = COMPRESSION_PROMPT_TEMPLATE.format(
            items=chunk_text,
            protected_terms=protected_terms,
        )

        try:
            response = context.llm_client.chat(compress_prompt)
            compressed = parse_list_response(response, min_words=config.min_words_per_item)

            # Fallback if parsing failed
            if not compressed:
                return chunk

            return compressed

        except Exception as e:
            print(f"    Warning: Compression failed: {e}")
            return chunk

    def _validate_and_restore(
        self,
        compressed: List[str],
        original_items: List[str],
        dates: Set[str],
        entities: Set[str],
        date_sources: Dict[str, str],
        entity_sources: Dict[str, str],
    ) -> List[str]:
        """Verify critical items survived compression and restore if missing.

        Args:
            compressed: Compressed items.
            original_items: Original items for restoration.
            dates: Protected dates.
            entities: Protected entities.
            date_sources: Mapping of dates to original items.
            entity_sources: Mapping of entities to original items.

        Returns:
            Compressed items with missing protected content restored.
        """
        full_text = " ".join(compressed).lower()
        restored = list(compressed)
        items_to_restore: Set[str] = set()

        # Check for missing dates - these are critical
        for date in dates:
            date_lower = date.lower()
            date_slash = date.replace("-", "/").lower()
            if date_lower not in full_text and date_slash not in full_text:
                if date in date_sources:
                    items_to_restore.add(date_sources[date])
                    print(f"    Restoring item for missing date: {date}")

        # Check for missing critical entities
        missing_entities = []
        for entity in entities:
            if entity.lower() not in full_text:
                missing_entities.append(entity)

        # If we lost significant entities, restore their source items
        if missing_entities and len(missing_entities) > len(entities) * 0.2:
            print(f"    Compression lost {len(missing_entities)} entities, restoring sources")
            for entity in missing_entities[:5]:
                if entity in entity_sources:
                    items_to_restore.add(entity_sources[entity])

        # Add restored items (avoid duplicates)
        for item in items_to_restore:
            item_lower = item.lower()
            already_present = any(
                item_lower in c.lower() or c.lower() in item_lower
                for c in restored
            )
            if not already_present:
                restored.append(f"[Restored] {item}")

        if items_to_restore:
            print(f"    Restored {len(items_to_restore)} items to preserve protected content")

        return restored

    def _drop_oldest_items(self, context: PipelineContext) -> None:
        """Drop oldest items that don't contain protected dates.

        Args:
            context: Pipeline context.
        """
        words_to_drop = (
            context.document.current_word_count() -
            int(context.config.max_words * 0.90)
        )

        if words_to_drop <= 0:
            return

        dropped_words = 0

        for section_name in context.document.sections:
            items = context.document.sections[section_name]
            if len(items) <= 1:
                continue

            # Identify items that can be dropped (no dates)
            droppable_indices = []
            for idx, item in enumerate(items):
                # Ensure item is a string
                item_str = str(item) if not isinstance(item, str) else item
                item_lower = item_str.lower()
                has_date = any(
                    date.lower() in item_lower or
                    date.replace("-", "/").lower() in item_lower
                    for date in context.document.tracked_dates
                )
                if not has_date:
                    droppable_indices.append(idx)

            # Drop from oldest until we've freed enough words
            items_to_remove = []
            for idx in droppable_indices:
                if dropped_words >= words_to_drop:
                    break
                item = items[idx]
                # Ensure item is a string
                item_str = str(item) if not isinstance(item, str) else item
                dropped_words += len(item_str.split())
                items_to_remove.append(idx)

            # Remove items (in reverse order to preserve indices)
            for idx in sorted(items_to_remove, reverse=True):
                removed = items.pop(idx)
                # Ensure removed is a string
                removed_str = str(removed) if not isinstance(removed, str) else removed
                print(f"    Dropped from {section_name}: {removed_str[:50]}...")

            if dropped_words >= words_to_drop:
                break
