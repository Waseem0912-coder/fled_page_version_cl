"""Finalize stage - generates the final report from consolidated extractions."""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from livedoc.core.stage import PipelineStage
from livedoc.core.context import PipelineContext
from livedoc.config.settings import (
    TOKEN_BUDGET_TOTAL,
    TOKEN_BUDGET_CONTENT,
    estimate_tokens,
    CHARS_PER_TOKEN,
)


# Importance-grouped finalize prompt template
FINALIZE_PROMPT = """You are an expert report writer. Synthesize this information into a coherent report.

CRITICAL (preserve exactly):
{critical}

HIGH PRIORITY:
{high}

TABLES (summarize key data):
{tables}

VISUAL INSIGHTS (charts/graphs):
{visuals}

SUPPORTING:
{medium}

{preferences}

RULES:
- Use ONLY the information above - never add external knowledge or assumptions
- Preserve all dates, names, figures exactly as given
- Write clear professional prose
- Skip topics with no information rather than speculate
- Target: {target_words} words

Write the report:"""


# Default instructions when user_preferences.txt is empty
DEFAULT_PREFERENCES = """Generate a detailed executive report (~800-1000 words) for stakeholders and leadership.

Include: Executive Summary, Background, Key Events (chronological), Impact Analysis, Root Cause, Current Status, Recommended Actions.

Tone: Professional, factual, suitable for board-level review."""


class FinalizeStage(PipelineStage):
    """Pipeline stage that generates the final report from extractions.

    Replaces the old Integrate->Compress->Perspective flow with a single
    synthesis step that:
    - Groups content by importance (critical, high, medium)
    - Handles multiple content types (tables, visuals, events, facts)
    - Respects token budgets and user preferences
    """

    @property
    def name(self) -> str:
        return "finalize"

    def should_skip(self, context: PipelineContext) -> bool:
        """Skip if no extractions available."""
        return not context.extractions

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Generate final report from extractions.

        Args:
            context: Pipeline context with extractions.

        Returns:
            Updated context with report generated.
        """
        print("\n--- Stage: Finalizing Report ---")

        # Consolidate all extractions by importance
        critical, high, medium, tables, visuals = self._consolidate_extractions(
            context.extractions
        )
        print(f"  Consolidated {len(context.extractions)} pages")
        print(f"    Critical: {len(critical)}, High: {len(high)}, Medium: {len(medium)}")
        print(f"    Tables: {len(tables)}, Visuals: {len(visuals)}")

        # Load user preferences
        preferences = self._load_preferences(context)

        # Build prompt within token budget
        prompt = self._build_prompt(
            critical,
            high,
            medium,
            tables,
            visuals,
            preferences,
            context.config.max_words,
        )

        token_estimate = estimate_tokens(prompt)
        print(f"  Prompt size: ~{token_estimate} tokens")

        if token_estimate > TOKEN_BUDGET_TOTAL:
            print(f"  Warning: Prompt exceeds budget, truncating content...")
            prompt = self._truncate_to_budget(
                critical, high, medium, tables, visuals,
                preferences, context.config.max_words
            )

        # Generate the report
        try:
            report = context.llm_client.chat(prompt)
            context.final_report = report.strip()
            print(f"  Generated report: {len(context.final_report.split())} words")
        except Exception as e:
            print(f"  Error generating report: {e}")
            # Fallback: create basic report from consolidated data
            context.final_report = self._fallback_report(
                critical, high, medium, tables, visuals
            )

        return context

    def _consolidate_extractions(
        self, extractions: List[Dict[str, Any]]
    ) -> Tuple[List[str], List[str], List[str], List[str], List[str]]:
        """Consolidate all page extractions by importance level.

        Groups content into critical (importance 3), high (2), and medium (1),
        plus separate lists for tables and visuals.

        Args:
            extractions: List of page extraction dicts.

        Returns:
            Tuple of (critical, high, medium, tables, visuals) lists.
        """
        critical: List[str] = []
        high: List[str] = []
        medium: List[str] = []
        tables: List[str] = []
        visuals: List[str] = []

        # Track seen items for deduplication
        seen_events: set = set()
        seen_facts: set = set()

        for ext in extractions:
            # Process events by importance
            for event in ext.get("events", []):
                if isinstance(event, dict):
                    summary = event.get("summary", "")
                    if not summary or self._get_signature(summary) in seen_events:
                        continue
                    seen_events.add(self._get_signature(summary))

                    importance = event.get("importance", 2)
                    item = self._format_event(event)

                    if importance >= 3:
                        critical.append(item)
                    elif importance >= 2:
                        high.append(item)
                    else:
                        medium.append(item)

            # Process tables
            for table in ext.get("tables", []):
                if isinstance(table, dict):
                    formatted = self._format_table(table)
                    if formatted:
                        tables.append(formatted)

            # Process visuals (charts, graphs, images)
            for visual in ext.get("visuals", []):
                if isinstance(visual, dict):
                    formatted = self._format_visual(visual)
                    if formatted:
                        visuals.append(formatted)

            # Process facts by importance
            for fact in ext.get("facts", []):
                if isinstance(fact, dict):
                    text = fact.get("text", "")
                    if not text or self._get_signature(text) in seen_facts:
                        continue
                    seen_facts.add(self._get_signature(text))

                    importance = fact.get("importance", 1)
                    if importance >= 3:
                        critical.append(text)
                    elif importance >= 2:
                        high.append(text)
                    else:
                        medium.append(text)
                elif isinstance(fact, str):
                    if fact and self._get_signature(fact) not in seen_facts:
                        seen_facts.add(self._get_signature(fact))
                        medium.append(fact)

            # Process key_facts (backward compatibility)
            for fact in ext.get("key_facts", []):
                if isinstance(fact, str):
                    if fact and self._get_signature(fact) not in seen_facts:
                        seen_facts.add(self._get_signature(fact))
                        medium.append(fact)

        return critical, high, medium, tables, visuals

    def _get_signature(self, text: str) -> str:
        """Get a signature for deduplication.

        Args:
            text: Text to get signature for.

        Returns:
            Lowercase first 50 chars as signature.
        """
        return text.lower()[:50]

    def _format_event(self, event: Dict[str, Any]) -> str:
        """Format an event for the prompt.

        Args:
            event: Event dictionary.

        Returns:
            Formatted event string.
        """
        date = event.get("date", "")
        summary = event.get("summary", "")
        actors = event.get("actors", [])

        date_str = f"[{date}] " if date else ""
        actor_str = f" ({', '.join(actors[:3])})" if actors else ""

        return f"{date_str}{summary}{actor_str}"

    def _format_table(self, table: Dict[str, Any]) -> str:
        """Format a table for the prompt.

        Args:
            table: Table dictionary with headers, rows, summary.

        Returns:
            Formatted table string.
        """
        summary = table.get("summary", "")
        headers = table.get("headers", [])
        rows = table.get("rows", [])

        if not summary and not headers:
            return ""

        header_str = ", ".join(headers[:5]) if headers else "data"
        row_count = len(rows)

        if summary:
            return f"Table ({header_str}, {row_count} rows): {summary}"
        else:
            # Generate brief summary from first row if available
            if rows and rows[0]:
                sample = ", ".join(str(cell)[:20] for cell in rows[0][:3])
                return f"Table ({header_str}): Sample data: {sample}..."
            return f"Table with columns: {header_str}"

    def _format_visual(self, visual: Dict[str, Any]) -> str:
        """Format a visual element for the prompt.

        Args:
            visual: Visual dictionary with type, description, trend.

        Returns:
            Formatted visual string.
        """
        vtype = visual.get("type", "visual")
        desc = visual.get("description", "")
        trend = visual.get("trend", "")
        data_points = visual.get("data_points", [])

        if not desc:
            return ""

        trend_str = f" - Trend: {trend}" if trend and trend != "n/a" else ""
        data_str = ""
        if data_points:
            data_str = f" Key values: {', '.join(data_points[:5])}"

        return f"{vtype.title()}: {desc}{trend_str}{data_str}"

    def _load_preferences(self, context: PipelineContext) -> str:
        """Load user preferences from txt file.

        Args:
            context: Pipeline context.

        Returns:
            Preferences string (or default if empty/missing).
        """
        pref_path = context.config.user_preferences_path
        if not pref_path:
            # Try default location
            pref_path = Path("user_preferences.txt")

        if pref_path and pref_path.exists():
            content = pref_path.read_text().strip()
            # Filter out comment lines
            lines = [
                line for line in content.split("\n")
                if line.strip() and not line.strip().startswith("#")
            ]
            user_prefs = "\n".join(lines).strip()
            if user_prefs:
                print(f"  Using user preferences from {pref_path}")
                return f"USER PREFERENCES:\n{user_prefs}"

        print("  Using default report format (detailed executive report)")
        return DEFAULT_PREFERENCES

    def _build_prompt(
        self,
        critical: List[str],
        high: List[str],
        medium: List[str],
        tables: List[str],
        visuals: List[str],
        preferences: str,
        max_words: int,
    ) -> str:
        """Build the finalize prompt.

        Args:
            critical: Critical importance items.
            high: High importance items.
            medium: Medium importance items.
            tables: Formatted table strings.
            visuals: Formatted visual strings.
            preferences: User preferences or default.
            max_words: Target word count.

        Returns:
            Complete prompt string.
        """
        return FINALIZE_PROMPT.format(
            critical=self._format_list(critical) or "(none)",
            high=self._format_list(high) or "(none)",
            medium=self._format_list(medium[:20]) or "(none)",  # Limit medium items
            tables=self._format_list(tables) or "(none)",
            visuals=self._format_list(visuals) or "(none)",
            preferences=preferences,
            target_words=max_words,
        )

    def _format_list(self, items: List[str]) -> str:
        """Format a list of items as bullet points.

        Args:
            items: List of strings.

        Returns:
            Bullet-point formatted string.
        """
        if not items:
            return ""
        return "\n".join(f"- {item}" for item in items if item)

    def _truncate_to_budget(
        self,
        critical: List[str],
        high: List[str],
        medium: List[str],
        tables: List[str],
        visuals: List[str],
        preferences: str,
        max_words: int,
    ) -> str:
        """Truncate content to fit within token budget.

        Prioritizes critical content, then high, then tables/visuals, then medium.

        Args:
            critical: Critical items (never truncated).
            high: High importance items.
            medium: Medium importance items.
            tables: Table summaries.
            visuals: Visual descriptions.
            preferences: User preferences.
            max_words: Target word count.

        Returns:
            Truncated prompt that fits budget.
        """
        # Calculate overhead (prompt template without content)
        overhead = estimate_tokens(
            FINALIZE_PROMPT.format(
                critical="", high="", medium="", tables="", visuals="",
                preferences=preferences, target_words=max_words
            )
        )
        available_tokens = TOKEN_BUDGET_CONTENT - overhead
        available_chars = available_tokens * CHARS_PER_TOKEN

        # Build content prioritizing critical items
        parts = []
        used_chars = 0

        # Critical items first (never skip)
        critical_text = self._format_list(critical)
        parts.append(("critical", critical_text))
        used_chars += len(critical_text)

        # High importance
        high_text = self._format_list(high)
        if used_chars + len(high_text) < available_chars * 0.6:
            parts.append(("high", high_text))
            used_chars += len(high_text)
        else:
            # Truncate high items
            truncated_high = self._truncate_items(high, int(available_chars * 0.3))
            parts.append(("high", truncated_high))
            used_chars += len(truncated_high)

        # Tables and visuals
        tables_text = self._format_list(tables)
        visuals_text = self._format_list(visuals)
        combined_visual = len(tables_text) + len(visuals_text)

        if used_chars + combined_visual < available_chars * 0.8:
            parts.append(("tables", tables_text))
            parts.append(("visuals", visuals_text))
            used_chars += combined_visual
        else:
            # Truncate tables/visuals
            budget = int((available_chars - used_chars) * 0.5)
            parts.append(("tables", self._truncate_items(tables, budget // 2)))
            parts.append(("visuals", self._truncate_items(visuals, budget // 2)))

        # Medium items with remaining budget
        remaining = available_chars - used_chars
        medium_text = self._truncate_items(medium, int(remaining * 0.8))
        parts.append(("medium", medium_text))

        # Build final prompt
        content_map = {name: text for name, text in parts}
        return FINALIZE_PROMPT.format(
            critical=content_map.get("critical") or "(none)",
            high=content_map.get("high") or "(none)",
            medium=content_map.get("medium") or "(none)",
            tables=content_map.get("tables") or "(none)",
            visuals=content_map.get("visuals") or "(none)",
            preferences=preferences,
            target_words=max_words,
        )

    def _truncate_items(self, items: List[str], max_chars: int) -> str:
        """Truncate a list of items to fit within character limit.

        Args:
            items: List of strings.
            max_chars: Maximum total characters.

        Returns:
            Formatted string within limit.
        """
        result = []
        total = 0

        for item in items:
            line = f"- {item}"
            if total + len(line) > max_chars:
                if result:
                    result.append("- ... (truncated)")
                break
            result.append(line)
            total += len(line) + 1  # +1 for newline

        return "\n".join(result)

    def _fallback_report(
        self,
        critical: List[str],
        high: List[str],
        medium: List[str],
        tables: List[str],
        visuals: List[str],
    ) -> str:
        """Generate a basic report when LLM fails.

        Args:
            critical: Critical items.
            high: High importance items.
            medium: Medium importance items.
            tables: Table summaries.
            visuals: Visual descriptions.

        Returns:
            Basic formatted report.
        """
        sections = ["# Report\n"]

        if critical:
            sections.append("## Critical Information\n")
            sections.append(self._format_list(critical))
            sections.append("")

        if high:
            sections.append("## Key Details\n")
            sections.append(self._format_list(high))
            sections.append("")

        if tables:
            sections.append("## Tables\n")
            sections.append(self._format_list(tables))
            sections.append("")

        if visuals:
            sections.append("## Visual Content\n")
            sections.append(self._format_list(visuals))
            sections.append("")

        if medium:
            sections.append("## Supporting Information\n")
            sections.append(self._format_list(medium[:15]))
            sections.append("")

        sections.append("---")
        sections.append("Note: This is a raw extraction. The LLM synthesis step was unable to complete.")

        return "\n".join(sections)
