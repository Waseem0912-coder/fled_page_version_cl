"""Date and event management utilities for preserving dates and events during compression."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class NormalizedDate:
    """Represents a normalized date with metadata.

    Attributes:
        original: Original date string as found in the document.
        normalized: ISO format date string (YYYY-MM-DD) or partial.
        year: Year component (may be None if not specified).
        month: Month component (may be None if not specified).
        day: Day component (may be None if not specified).
        confidence: Confidence level (1.0 = certain, 0.5 = inferred).
        inferred: Whether any component was inferred from context.
    """

    original: str
    normalized: str
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    confidence: float = 1.0
    inferred: bool = False


@dataclass
class EnrichedEvent:
    """Represents an event with normalized date and semantic signature.

    Attributes:
        date: Normalized date information.
        event_type: Type of event (incident, decision, action, other).
        summary: Event summary text.
        actors: List of actor names involved.
        importance: Importance level (1-3).
        semantic_signature: Signature for deduplication.
        date_context: Surrounding context for year inference.
    """

    date: Optional[NormalizedDate] = None
    event_type: str = "other"
    summary: str = ""
    actors: List[str] = field(default_factory=list)
    importance: int = 2
    semantic_signature: str = ""
    date_context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date.normalized if self.date else None,
            "type": self.event_type,
            "summary": self.summary,
            "actors": self.actors,
            "importance": self.importance,
        }


class DateEventManager:
    """Manager for date parsing, event enrichment, and deduplication.

    Provides utilities for:
    - Parsing various date formats to normalized ISO format
    - Enriching events with normalized dates and semantic signatures
    - Deduplicating events based on semantic similarity
    - Inferring missing years from surrounding context
    """

    # Common date patterns
    DATE_PATTERNS = [
        # ISO format: 2023-03-15
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'iso'),
        # US format: 03/15/2023 or 3/15/23
        (r'(\d{1,2})/(\d{1,2})/(\d{2,4})', 'us'),
        # EU format: 15/03/2023 or 15.03.2023
        (r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})', 'eu'),
        # Written: March 15, 2023 or Mar 15 2023
        (r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
         r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
         r'Dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?[,\s]+(\d{4})', 'written_full'),
        # Written without year: March 15 or Mar 15
        (r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
         r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
         r'Dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?(?!\d)', 'written_no_year'),
        # Day Month Year: 15 March 2023
        (r'(\d{1,2})(?:st|nd|rd|th)?\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|'
         r'Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|'
         r'Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[,\s]+(\d{4})', 'eu_written'),
        # Year only: 2023
        (r'\b(20\d{2})\b', 'year_only'),
        # Month Year: March 2023
        (r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
         r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
         r'Dec(?:ember)?)\s+(\d{4})', 'month_year'),
    ]

    MONTH_MAP = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
    }

    def __init__(self, document_year: Optional[int] = None):
        """Initialize the DateEventManager.

        Args:
            document_year: Default year context from the document.
        """
        self.document_year = document_year or datetime.now().year
        self._seen_years: Set[int] = set()

    def parse_date(
        self,
        date_str: str,
        context_year: Optional[int] = None,
    ) -> Optional[NormalizedDate]:
        """Parse a date string into a normalized format.

        Args:
            date_str: Date string to parse.
            context_year: Year context for partial dates.

        Returns:
            NormalizedDate or None if parsing failed.
        """
        if not date_str:
            return None

        date_str = str(date_str).strip()
        if not date_str:
            return None

        year_context = context_year or self.document_year

        for pattern, format_type in self.DATE_PATTERNS:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                return self._parse_match(match, format_type, date_str, year_context)

        # Fallback: return original with low confidence
        return NormalizedDate(
            original=date_str,
            normalized=date_str,
            confidence=0.3,
        )

    def _parse_match(
        self,
        match: re.Match,
        format_type: str,
        original: str,
        year_context: int,
    ) -> NormalizedDate:
        """Parse a regex match into NormalizedDate.

        Args:
            match: Regex match object.
            format_type: Type of date format matched.
            original: Original date string.
            year_context: Year context for partial dates.

        Returns:
            NormalizedDate object.
        """
        year = month = day = None
        inferred = False
        confidence = 1.0

        if format_type == 'iso':
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))

        elif format_type == 'us':
            month = int(match.group(1))
            day = int(match.group(2))
            year = self._normalize_year(match.group(3))

        elif format_type == 'eu':
            # Heuristic: if first number > 12, it's likely day-first
            first = int(match.group(1))
            second = int(match.group(2))
            if first > 12:
                day = first
                month = second
            elif second > 12:
                month = first
                day = second
            else:
                # Ambiguous, assume EU format (day/month)
                day = first
                month = second
                confidence = 0.8
            year = self._normalize_year(match.group(3))

        elif format_type == 'written_full':
            month = self._month_to_int(match.group(1))
            day = int(match.group(2))
            year = int(match.group(3))

        elif format_type == 'written_no_year':
            month = self._month_to_int(match.group(1))
            day = int(match.group(2))
            year = year_context
            inferred = True
            confidence = 0.7

        elif format_type == 'eu_written':
            day = int(match.group(1))
            month = self._month_to_int(match.group(2))
            year = int(match.group(3))

        elif format_type == 'year_only':
            year = int(match.group(1))
            confidence = 0.5

        elif format_type == 'month_year':
            month = self._month_to_int(match.group(1))
            year = int(match.group(2))
            confidence = 0.8

        # Track seen years for context
        if year:
            self._seen_years.add(year)

        # Build normalized string
        normalized = self._build_normalized(year, month, day)

        return NormalizedDate(
            original=original,
            normalized=normalized,
            year=year,
            month=month,
            day=day,
            confidence=confidence,
            inferred=inferred,
        )

    def _normalize_year(self, year_str: str) -> int:
        """Normalize 2-digit year to 4-digit year.

        Args:
            year_str: Year string (2 or 4 digits).

        Returns:
            4-digit year.
        """
        year = int(year_str)
        if year < 100:
            # Assume 2000s for 00-50, 1900s for 51-99
            if year <= 50:
                year += 2000
            else:
                year += 1900
        return year

    def _month_to_int(self, month_str: str) -> int:
        """Convert month name to integer.

        Args:
            month_str: Month name (full or abbreviated).

        Returns:
            Month number (1-12).
        """
        return self.MONTH_MAP.get(month_str.lower()[:3], 1)

    def _build_normalized(
        self,
        year: Optional[int],
        month: Optional[int],
        day: Optional[int],
    ) -> str:
        """Build normalized ISO date string.

        Args:
            year: Year component.
            month: Month component.
            day: Day component.

        Returns:
            Normalized date string.
        """
        if year and month and day:
            return f"{year:04d}-{month:02d}-{day:02d}"
        elif year and month:
            return f"{year:04d}-{month:02d}"
        elif year:
            return f"{year:04d}"
        else:
            return ""

    def enrich_event(
        self,
        event: Dict[str, Any],
        context_year: Optional[int] = None,
    ) -> EnrichedEvent:
        """Convert raw event dict to EnrichedEvent.

        Args:
            event: Raw event dictionary from extraction.
            context_year: Year context for partial dates.

        Returns:
            EnrichedEvent with normalized date and semantic signature.
        """
        # Parse date
        date_str = event.get("date")
        normalized_date = None
        if date_str:
            normalized_date = self.parse_date(date_str, context_year)

        # Extract other fields
        summary = str(event.get("summary", ""))
        actors = event.get("actors", [])
        if not isinstance(actors, list):
            actors = [str(actors)] if actors else []
        actors = [str(a) for a in actors if a]

        event_type = str(event.get("type", "other"))
        importance = self._normalize_importance(event.get("importance", 2))

        # Build semantic signature
        signature = self._build_semantic_signature(summary, normalized_date, actors)

        return EnrichedEvent(
            date=normalized_date,
            event_type=event_type,
            summary=summary,
            actors=actors,
            importance=importance,
            semantic_signature=signature,
        )

    def _build_semantic_signature(
        self,
        summary: str,
        date: Optional[NormalizedDate],
        actors: List[str],
    ) -> str:
        """Build semantic signature for deduplication.

        The signature captures the key semantic content of an event,
        allowing detection of duplicates that may have different wording.

        Args:
            summary: Event summary text.
            date: Normalized date (if available).
            actors: List of actors.

        Returns:
            Semantic signature string.
        """
        # Extract key words from summary (nouns, verbs, important terms)
        # Remove common stop words and normalize
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'was', 'were', 'is', 'are', 'been', 'be',
            'has', 'have', 'had', 'this', 'that', 'these', 'those', 'it', 'its',
            'which', 'who', 'what', 'when', 'where', 'why', 'how',
        }

        # Normalize and extract key terms
        words = re.findall(r'\b[a-zA-Z]+\b', summary.lower())
        key_terms = [w for w in words if w not in stop_words and len(w) > 2]
        key_terms = sorted(set(key_terms))[:8]  # Limit to 8 key terms

        # Include date if available
        date_part = date.normalized if date else ""

        # Include normalized actor names
        actor_part = ",".join(sorted(a.lower()[:20] for a in actors[:3]))

        # Combine into signature
        return f"{date_part}|{','.join(key_terms)}|{actor_part}"

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

    def deduplicate_events(
        self,
        events: List[EnrichedEvent],
        similarity_threshold: float = 0.7,
    ) -> List[EnrichedEvent]:
        """Deduplicate events based on semantic signatures.

        Events with similar signatures are merged, keeping the one with
        higher importance or more complete information.

        Args:
            events: List of enriched events.
            similarity_threshold: Minimum similarity to consider duplicate.

        Returns:
            Deduplicated list of events.
        """
        if not events:
            return []

        # Group by date first for efficiency
        date_groups: Dict[str, List[EnrichedEvent]] = {}
        for event in events:
            date_key = event.date.normalized[:7] if event.date else "no_date"
            if date_key not in date_groups:
                date_groups[date_key] = []
            date_groups[date_key].append(event)

        result: List[EnrichedEvent] = []
        seen_signatures: Set[str] = set()

        for date_key, group in date_groups.items():
            # Sort by importance (highest first)
            group.sort(key=lambda e: e.importance, reverse=True)

            for event in group:
                # Check if similar event already seen
                if self._is_duplicate(event, seen_signatures, similarity_threshold):
                    continue

                seen_signatures.add(event.semantic_signature)
                result.append(event)

        # Sort by date
        result.sort(key=lambda e: e.date.normalized if e.date else "9999")

        return result

    def _is_duplicate(
        self,
        event: EnrichedEvent,
        seen_signatures: Set[str],
        threshold: float,
    ) -> bool:
        """Check if event is a duplicate of any seen event.

        Args:
            event: Event to check.
            seen_signatures: Set of seen semantic signatures.
            threshold: Similarity threshold.

        Returns:
            True if event is a duplicate.
        """
        sig_parts = event.semantic_signature.split("|")
        if len(sig_parts) < 2:
            return event.semantic_signature in seen_signatures

        event_terms = set(sig_parts[1].split(","))

        for seen_sig in seen_signatures:
            seen_parts = seen_sig.split("|")
            if len(seen_parts) < 2:
                continue

            # Check date match (must be same or within range)
            if sig_parts[0] and seen_parts[0]:
                if sig_parts[0][:7] != seen_parts[0][:7]:
                    continue

            # Check term overlap
            seen_terms = set(seen_parts[1].split(","))
            if not event_terms or not seen_terms:
                continue

            overlap = len(event_terms & seen_terms)
            similarity = overlap / max(len(event_terms), len(seen_terms))

            if similarity >= threshold:
                return True

        return False

    def infer_missing_years(
        self,
        events: List[EnrichedEvent],
        document_year: Optional[int] = None,
    ) -> List[EnrichedEvent]:
        """Infer missing years from surrounding context.

        Uses the years found in other events and document context
        to fill in missing year information.

        Args:
            events: List of enriched events.
            document_year: Default year from document.

        Returns:
            Events with inferred years where possible.
        """
        if not events:
            return events

        # Collect all explicit years
        explicit_years = set()
        for event in events:
            if event.date and event.date.year and not event.date.inferred:
                explicit_years.add(event.date.year)

        # Determine most likely year
        if explicit_years:
            # Use most common year or most recent
            likely_year = max(explicit_years)
        elif document_year:
            likely_year = document_year
        else:
            likely_year = self.document_year

        # Infer missing years
        for event in events:
            if event.date and not event.date.year:
                # Create new date with inferred year
                event.date = NormalizedDate(
                    original=event.date.original,
                    normalized=self._build_normalized(
                        likely_year, event.date.month, event.date.day
                    ),
                    year=likely_year,
                    month=event.date.month,
                    day=event.date.day,
                    confidence=event.date.confidence * 0.8,
                    inferred=True,
                )

        return events

    def extract_all_dates(self, text: str) -> List[NormalizedDate]:
        """Extract all dates from a text string.

        Args:
            text: Text to search for dates.

        Returns:
            List of all found dates.
        """
        dates = []
        for pattern, format_type in self.DATE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                date = self._parse_match(
                    match, format_type, match.group(0), self.document_year
                )
                if date and date.normalized:
                    dates.append(date)

        # Deduplicate by normalized value
        seen = set()
        unique_dates = []
        for date in dates:
            if date.normalized not in seen:
                seen.add(date.normalized)
                unique_dates.append(date)

        return unique_dates

    def get_date_variants(self, date: NormalizedDate) -> Set[str]:
        """Get all variants of a date for matching.

        Args:
            date: Normalized date.

        Returns:
            Set of date string variants for matching.
        """
        variants = {date.original, date.normalized}

        if date.year and date.month and date.day:
            # Add common format variants
            variants.add(f"{date.month}/{date.day}/{date.year}")
            variants.add(f"{date.day}/{date.month}/{date.year}")
            variants.add(f"{date.month}-{date.day}-{date.year}")

            # Add month name variants
            month_names = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]
            if 1 <= date.month <= 12:
                month_name = month_names[date.month - 1]
                variants.add(f"{month_name} {date.day}, {date.year}")
                variants.add(f"{date.day} {month_name} {date.year}")
                variants.add(f"{month_name[:3]} {date.day}, {date.year}")

        return variants


def sort_events_by_importance(
    events: List[Dict[str, Any]],
    max_count: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Sort events by importance score, keeping highest importance first.

    Args:
        events: List of event dictionaries.
        max_count: Maximum number of events to return.

    Returns:
        Sorted list of events (highest importance first).
    """
    if not events:
        return []

    # Sort by importance (descending), then by date if available
    def sort_key(event: Dict[str, Any]) -> Tuple[int, str]:
        importance = event.get("importance", 2)
        if not isinstance(importance, int):
            try:
                importance = int(importance)
            except (ValueError, TypeError):
                importance = 2
        # Negate importance for descending sort
        date = event.get("date", "9999")
        return (-importance, str(date) if date else "9999")

    sorted_events = sorted(events, key=sort_key)

    if max_count:
        return sorted_events[:max_count]

    return sorted_events
