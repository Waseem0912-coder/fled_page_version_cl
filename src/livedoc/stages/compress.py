"""Compression stage - smart consolidation while preserving critical info."""

import re
from typing import Any, Dict, List, Set, Tuple

from livedoc.core.stage import PipelineStage
from livedoc.core.context import PipelineContext
from livedoc.config.settings import (
    CompressionConfig,
    TOKEN_BUDGET_CONTENT,
    estimate_tokens,
)
from livedoc.utils.parsing import parse_list_response
from livedoc.utils.date_event import DateEventManager


# Concise, effective compression prompt
CONSOLIDATE_PROMPT = """Consolidate these items into fewer, information-dense sentences.

ITEMS:
{items}

PROTECTED (must appear in output):
{protected}

{sequence_hint}

RULES:
1. Merge related items into single sentences
2. Keep ALL dates and names exactly as written
3. Remove redundancy and filler words
4. Output 3-8 consolidated items
5. Each item: 15-40 words, factual, complete
6. PRESERVE chronological order when events have dates
7. DO NOT merge events with different dates into one item

Output as a dash-prefixed list:
- consolidated item 1
- consolidated item 2"""


class CompressStage(PipelineStage):
    """Pipeline stage that consolidates content while preserving key info.

    Uses smart grouping and single-pass consolidation to minimize loss.
    Protected items (dates, entities) are always preserved.
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
        """Execute smart consolidation.

        Args:
            context: Pipeline context with document.

        Returns:
            Updated context with consolidated document.
        """
        if not context.document:
            return context

        initial = context.document.current_word_count()
        target = context.config.max_words
        print(f"Consolidating... ({initial} words -> target {target})")

        # Process each section
        for section_name, items in context.document.sections.items():
            if len(items) < 3:
                continue

            # Group similar items first
            groups = self._group_similar_items(items)

            # Consolidate each group
            consolidated = []
            for group in groups:
                if len(group) == 1:
                    consolidated.append(group[0])
                else:
                    merged = self._consolidate_group(
                        group,
                        context.document.tracked_dates,
                        context.document.tracked_entities,
                        context,
                    )
                    consolidated.extend(merged)

            context.document.sections[section_name] = consolidated

        # Verify protected items survived
        self._verify_protected(context)

        final = context.document.current_word_count()
        print(f"After consolidation: {final} words")

        # Only if still over limit, do targeted reduction
        if final > target:
            self._targeted_reduction(context, target)

        return context

    def _group_similar_items(self, items: List[str]) -> List[List[str]]:
        """Group items by semantic similarity.

        Args:
            items: List of content items.

        Returns:
            List of groups (each group is a list of similar items).
        """
        if len(items) <= 3:
            return [items]

        groups: List[List[str]] = []
        used = set()

        for i, item in enumerate(items):
            if i in used:
                continue

            group = [item]
            used.add(i)
            item_words = set(self._normalize(item).split())

            # Find similar items
            for j, other in enumerate(items):
                if j in used:
                    continue
                other_words = set(self._normalize(other).split())
                overlap = len(item_words & other_words)
                # Group if significant word overlap
                if overlap >= 3 or (overlap >= 2 and len(item_words) < 10):
                    group.append(other)
                    used.add(j)
                    if len(group) >= 5:  # Cap group size
                        break

            groups.append(group)

        return groups

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        text = str(text) if not isinstance(text, str) else text
        # Remove common words and punctuation
        stop = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = [w.lower().strip('.,;:!?') for w in text.split()]
        return ' '.join(w for w in words if w not in stop and len(w) > 2)

    def _consolidate_group(
        self,
        group: List[str],
        dates: Set[str],
        entities: Set[str],
        context: PipelineContext,
    ) -> List[str]:
        """Consolidate a group of similar items.

        Args:
            group: Items to consolidate.
            dates: Protected dates.
            entities: Protected entities.
            context: Pipeline context.

        Returns:
            Consolidated items (fewer than input).
        """
        if len(group) <= 2:
            return group

        # Find which protected items are in this group using word-boundary matching
        group_text = " ".join(str(g) for g in group)
        relevant_dates = self._find_matching_items(dates, group_text)
        relevant_entities = self._find_matching_items(entities, group_text)

        protected = []
        if relevant_dates:
            protected.append(f"Dates: {', '.join(relevant_dates[:5])}")
        if relevant_entities:
            protected.append(f"Names: {', '.join(relevant_entities[:5])}")
        protected_str = "\n".join(protected) if protected else "None specified"

        # Detect event sequences and build hint
        sequence_hint = self._detect_event_sequence(group)

        # Build prompt
        items_str = "\n".join(f"- {str(item)}" for item in group)

        # Check token budget
        prompt = CONSOLIDATE_PROMPT.format(
            items=items_str,
            protected=protected_str,
            sequence_hint=sequence_hint,
        )
        if estimate_tokens(prompt) > TOKEN_BUDGET_CONTENT:
            # Split group in half and process separately
            mid = len(group) // 2
            left = self._consolidate_group(group[:mid], dates, entities, context)
            right = self._consolidate_group(group[mid:], dates, entities, context)
            return left + right

        try:
            response = context.llm_client.chat(prompt)
            result = parse_list_response(response, min_words=5)
            if result:
                return result
        except Exception as e:
            print(f"  Consolidation warning: {e}")

        # Fallback: return original
        return group

    def _find_matching_items(self, items: Set[str], text: str) -> List[str]:
        """Find items that match in text using word-boundary regex.

        Uses word-boundary matching instead of simple substring matching
        to avoid false positives (e.g., "Jan" matching "January" in wrong context).

        Args:
            items: Set of items to find.
            text: Text to search in.

        Returns:
            List of matching items.
        """
        matches = []
        for item in items:
            # Escape special regex characters and create word-boundary pattern
            escaped = re.escape(str(item))
            # Use word boundaries for alphanumeric items, but be flexible for dates
            if re.search(r'^\d', item):
                # For dates, use looser matching (allow surrounding punctuation)
                pattern = rf'(?:^|[\s,;:\[\(]){escaped}(?:[\s,;:\]\)]|$)'
            else:
                # For names/entities, use word boundaries
                pattern = rf'\b{escaped}\b'

            if re.search(pattern, text, re.IGNORECASE):
                matches.append(item)

        return matches

    def _detect_event_sequence(self, group: List[str]) -> str:
        """Detect if the group contains a sequence of chronological events.

        Extracts dates from items and determines if they form a sequence
        that should be preserved.

        Args:
            group: List of items to analyze.

        Returns:
            Hint string for the consolidation prompt.
        """
        date_manager = DateEventManager()
        dated_items: List[Tuple[str, str]] = []  # (date, item)

        for item in group:
            item_str = str(item)
            # Look for date patterns in brackets like [2023-01-15]
            bracket_match = re.search(r'\[(\d{4}-\d{2}-\d{2}[^\]]*)\]', item_str)
            if bracket_match:
                date_str = bracket_match.group(1)
                dated_items.append((date_str, item_str))
            else:
                # Try to find any date in the item
                dates = date_manager.extract_all_dates(item_str)
                if dates:
                    dated_items.append((dates[0].normalized, item_str))

        if len(dated_items) >= 2:
            # Check if dates are different (indicating a sequence)
            unique_dates = set(d[0][:10] for d in dated_items)
            if len(unique_dates) > 1:
                return "EVENT SEQUENCE DETECTED: These items contain different dates and represent a chronological sequence. Keep them separate."

        return ""

    def _verify_protected(self, context: PipelineContext) -> None:
        """Verify protected items survived and restore if needed.

        Uses word-boundary matching for more accurate detection.

        Args:
            context: Pipeline context.
        """
        if not context.document:
            return

        # Get all current text (preserve case for matching)
        all_text = " ".join(
            " ".join(str(item) for item in items)
            for items in context.document.sections.values()
        )

        # Check dates using word-boundary matching
        missing_dates = []
        date_manager = DateEventManager()
        for date in context.document.tracked_dates:
            # Get normalized variants of the date
            parsed = date_manager.parse_date(date)
            if parsed:
                variants = date_manager.get_date_variants(parsed)
            else:
                variants = {date, date.replace("-", "/")}

            # Check if any variant appears with word boundaries
            found = False
            for variant in variants:
                escaped = re.escape(str(variant))
                if re.search(rf'(?:^|[\s,;:\[\(]){escaped}(?:[\s,;:\]\)]|$)', all_text, re.IGNORECASE):
                    found = True
                    break

            if not found:
                missing_dates.append(date)

        if missing_dates:
            print(f"  Warning: {len(missing_dates)} dates missing after consolidation")
            # Add a restoration note to the first section with content
            for section, items in context.document.sections.items():
                if items:
                    items.append(f"[Key dates: {', '.join(missing_dates[:5])}]")
                    break

    def _targeted_reduction(self, context: PipelineContext, target: int) -> None:
        """Reduce word count through targeted removal.

        Uses word-boundary matching for protected content detection.

        Args:
            context: Pipeline context.
            target: Target word count.
        """
        current = context.document.current_word_count()
        excess = current - target

        if excess <= 0:
            return

        print(f"  Targeted reduction needed: {excess} words over limit")

        # Calculate how many items to remove per section
        for section, items in context.document.sections.items():
            if len(items) <= 2:
                continue

            # Score items by importance (dates and entities = higher score)
            scored = []
            for i, item in enumerate(items):
                item_str = str(item) if not isinstance(item, str) else item
                score = 0

                # Use word-boundary matching for dates
                for date in context.document.tracked_dates:
                    escaped = re.escape(str(date))
                    if re.search(rf'(?:^|[\s,;:\[\(]){escaped}(?:[\s,;:\]\)]|$)', item_str, re.IGNORECASE):
                        score += 10

                # Use word-boundary matching for entities
                for entity in context.document.tracked_entities:
                    escaped = re.escape(str(entity))
                    if re.search(rf'\b{escaped}\b', item_str, re.IGNORECASE):
                        score += 5

                scored.append((i, item_str, score))

            # Sort by score (lowest first = candidates for removal)
            scored.sort(key=lambda x: x[2])

            # Remove lowest-scored items until we've freed enough words
            removed_words = 0
            indices_to_remove = []
            for i, item_str, score in scored:
                if removed_words >= excess:
                    break
                if score < 5:  # Don't remove items with protected content
                    removed_words += len(item_str.split())
                    indices_to_remove.append(i)
                    if len(indices_to_remove) >= len(items) // 2:
                        break  # Don't remove more than half

            # Remove items
            for idx in sorted(indices_to_remove, reverse=True):
                removed = items.pop(idx)
                print(f"    Removed: {str(removed)[:50]}...")

            excess -= removed_words
            if excess <= 0:
                break
