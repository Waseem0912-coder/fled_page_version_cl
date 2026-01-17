# LiveDoc Report Generator

A flexible, vision-based PDF processing pipeline for generating structured reports from large document collections using local LLMs via Ollama.

---

## Overview

This system processes multiple PDFs (issue trackers, email dumps, chat logs, internal documents) into concise, formatted reports with configurable word limits and perspectives. It uses a **sequential processing architecture** designed for smaller vision-capable models (14B parameters) that cannot handle large context windows.

### Key Features

- **Vision-first extraction**: Converts PDFs to images for reliable text/layout extraction
- **Multi-content detection**: Automatically identifies tables, charts, graphs, images, and paragraphs
- **Unified extraction**: Single LLM call detects content types AND extracts structured data
- **Importance scoring**: All items scored 1-3 for smart compression prioritization
- **Type-specific handling**: Tables get structured data, charts get trends, visuals get descriptions
- **Rolling summary ("LiveDoc")**: Builds document incrementally to respect word limits
- **Smart compression**: Preserves critical items (importance 3) while compressing lower-priority content
- **Perspective rewriting**: Generate reports from different team member viewpoints
- **Local-first**: Runs entirely on local hardware via Ollama

### Hardware Requirements

- **Target**: NVIDIA RTX Ada 5000 (32GB VRAM)
- **Model**: `ministral-3-14B` (vision + text capable)
- **Minimum**: 16GB VRAM for inference with image inputs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  /input/                                                                     │
│  ├── documents/          # PDFs to process                                  │
│  │   ├── issue_tracker.pdf                                                  │
│  │   ├── email_dump.pdf                                                     │
│  │   └── chat_log.pdf                                                       │
│  ├── format.md           # User-defined output structure                    │
│  └── perspectives/       # Optional team viewpoint configs                  │
│      ├── engineering.md                                                     │
│      └── product.md                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STEP 1: PDF → IMAGE CONVERSION                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  Tool: pdftoppm (Poppler) or pdf2image                                      │
│  Output: /tmp/pages/doc_001_page_001.png, doc_001_page_002.png, ...         │
│  Resolution: 150 DPI (balance quality vs token cost)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                STEP 2: UNIFIED VISION EXTRACTION (Per Page)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Model: ministral-3-14B via Ollama                                          │
│  Input: Single page image + unified extraction prompt                       │
│  Output: Structured JSON with detected content types + extractions          │
│                                                                              │
│  DETECTION: Identifies content types on each page:                          │
│  - Tables (headers, rows, summary)                                          │
│  - Charts/Graphs (description, trend, data points)                          │
│  - Images/Diagrams (description, labels)                                    │
│  - Paragraphs (events, facts, entities)                                     │
│                                                                              │
│  page_001.json:                                                             │
│  {                                                                          │
│    "content_types": ["table", "paragraph"],                                 │
│    "tables": [{ "headers": ["Date", "Issue"], "rows": [...],                │
│                 "summary": "Timeline of incidents", "importance": 3 }],     │
│    "visuals": [{ "type": "chart", "description": "Error rate over time",    │
│                  "trend": "increasing", "importance": 2 }],                 │
│    "events": [{ "date": "2024-03-15", "type": "incident",                   │
│                 "summary": "Server outage", "importance": 3 }],             │
│    "entities": ["AWS", "us-east-1", "nginx"],                               │
│    "dates": ["2024-03-15"],                                                 │
│    "facts": [{ "text": "Load balancer timeout", "importance": 2 }],         │
│    "continues_previous": false, "continues_next": true                      │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     STEP 3: SEQUENTIAL LIVEDOC BUILD                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  Process: For each page JSON, decide: ADD | UPDATE | SKIP | COMPRESS        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  LiveDoc State (in memory)                                          │    │
│  │  ─────────────────────────────────────────────────────────────────  │    │
│  │  current_word_count: 847                                            │    │
│  │  max_words: 1500                                                    │    │
│  │  sections: { "Timeline": [...], "Key Issues": [...] }              │    │
│  │  tracked_entities: Set(["AWS", "nginx", ...])                       │    │
│  │  tracked_dates: ["2024-03-15", "2024-03-16", ...]                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Decision Flow (per page):                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │ Load page    │───▶│ Check if new │───▶│ ADD: Insert  │                  │
│  │ JSON summary │    │ information  │    │ new content  │                  │
│  └──────────────┘    └──────┬───────┘    └──────────────┘                  │
│                             │                                               │
│                      ┌──────▼───────┐    ┌──────────────┐                  │
│                      │ Check if     │───▶│ UPDATE:      │                  │
│                      │ contradicts/ │    │ Modify entry │                  │
│                      │ extends      │    └──────────────┘                  │
│                      └──────┬───────┘                                       │
│                             │                                               │
│                      ┌──────▼───────┐    ┌──────────────┐                  │
│                      │ Redundant?   │───▶│ SKIP: No     │                  │
│                      │              │    │ action       │                  │
│                      └──────┬───────┘    └──────────────┘                  │
│                             │                                               │
│                      ┌──────▼───────┐    ┌──────────────┐                  │
│                      │ Over word    │───▶│ COMPRESS:    │                  │
│                      │ limit?       │    │ Smart merge  │                  │
│                      └──────────────┘    └──────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 4: PERSPECTIVE REWRITE (Optional)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Trigger: --perspective engineering                                         │
│  Input: Final LiveDoc + perspectives/engineering.md                         │
│  Output: Rewritten report emphasizing team-specific concerns                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  /output/                                                                    │
│  ├── report.md           # Final formatted report                           │
│  ├── report_engineering.md  # Perspective variant                           │
│  └── extraction/         # Raw extraction JSONs (debug)                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Logic

### Why Sequential Processing?

A 14B parameter model cannot effectively process:
- 15+ pages of dense text simultaneously
- Multiple JSON extractions at once for comparison
- Full document context for compression decisions

**Solution**: Process one page at a time, maintaining state in a "LiveDoc" that the model can compare against. Each decision requires only:
1. Current page summary (small JSON)
2. Current LiveDoc state (within word limit)
3. Format template (fixed)

### Step 2: Extraction Strategy

Each page is processed independently. The model receives only the image and a structured prompt—no prior context needed.

**Why JSON output?**
- Structured data enables programmatic word counting
- Topics/entities enable smart compression (we know what's important)
- Dates extracted explicitly are never compressed away

### Step 3: Finalize (New Architecture)

When using `use_finalize_stage=True` (default), extractions are synthesized directly into the final report:

| Priority Level | Content | Handling |
|----------------|---------|----------|
| **CRITICAL (3)** | Dates, key decisions | Never truncated, preserved exactly |
| **HIGH (2)** | Important context | Included unless severe budget constraints |
| **MEDIUM (1)** | Supporting details | Truncated first when over budget |
| **TABLES** | Structured data | Summarized with key columns/rows |
| **VISUALS** | Charts/graphs/images | Trend + description preserved |

**Finalize Prompt Structure:**
```
CRITICAL (preserve exactly):
- [2024-03-15] Server outage detected (ops-team)

HIGH PRIORITY:
- Load balancer timeout after 30 seconds

TABLES (summarize key data):
- Table (Date, Issue, Status, 12 rows): Timeline of incident events

VISUAL INSIGHTS (charts/graphs):
- Chart: Error rate over time - Trend: increasing

SUPPORTING:
- Routine maintenance was scheduled for next week

{user_preferences}
Target: {target_words} words.
```

### Step 3 (Legacy): LiveDoc Operations

| Operation | When | What Happens |
|-----------|------|--------------|
| **ADD** | New event, date, or topic not in LiveDoc | Append to appropriate section |
| **UPDATE** | New info about existing event/entity | Merge details, update summary |
| **SKIP** | Duplicate/redundant information | No change to LiveDoc |
| **COMPRESS** | Word count exceeds threshold | Merge similar events, shorten descriptions |

**Compression Rules** (hardcoded, not LLM-decided):
- Dates are NEVER compressed or removed
- Entity names preserved verbatim
- Topic keywords preserved
- Only narrative descriptions shortened
- Older events compressed more aggressively than recent

### Step 4: Perspective Rewriting (Two Modes)

**Mode A: Section-Level Perspective**
- User specifies goals per section in a structured config
- Model generates tailored prompts per section based on goals
- Each section rewritten independently with section-specific emphasis

**Mode B: Global Perspective**  
- Single perspective applied to entire document
- One rewrite pass with overall voice/emphasis guidance

```
┌─────────────────────────────────────────────────────────────────┐
│  PERSPECTIVE MODE SELECTION                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  --perspective engineering                                      │
│  └── Mode B: Load perspectives/engineering.md, rewrite all     │
│                                                                 │
│  --perspective-sections perspectives/engineering_sections.yaml │
│  └── Mode A: Per-section goals, model adapts prompts           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration Files

### format.md (Required)

```markdown
# Report Format Specification

## Metadata
- title: "Incident Post-Mortem"
- max_words: 1500
- date_format: "YYYY-MM-DD"

## Structure

### Executive Summary
Max 100 words. High-level what happened and resolution status.

### Timeline
Chronological list of key events with dates. Required fields:
- Date
- Event description
- Actors involved

### Root Cause Analysis
Narrative explaining what went wrong. Emphasize technical details.

### Impact Assessment  
Quantify: downtime duration, users affected, revenue impact if known.

### Action Items
Bulleted list of follow-ups with owners and due dates.
```

### perspectives/engineering.md (Optional - Mode B: Global)

```markdown
# Engineering Perspective

## Voice
Write as a senior engineer addressing the engineering team.

## Emphasize
- Technical root causes and system behaviors
- Code/config changes that contributed
- Infrastructure dependencies
- Monitoring gaps

## De-emphasize
- Business impact metrics (mention briefly)
- Customer communication timelines
- Executive decisions

## Terminology
- Use technical terms without explanation
- Reference specific services by internal names
- Include relevant error codes/log snippets
```

### perspectives/engineering_sections.yaml (Optional - Mode A: Section-Level)

```yaml
# Section-level perspective control
# The model will read each goal and generate an appropriate rewrite prompt

meta:
  voice: "Senior engineer writing for engineering team"
  terminology: "technical, use internal service names"

sections:
  Executive Summary:
    goal: "Focus on technical summary - what broke, what fixed it"
    emphasize: ["root cause", "fix deployed"]
    max_words: 80
    
  Timeline:
    goal: "Keep all timestamps, add technical context to each event"
    emphasize: ["system states", "error codes", "deploy times"]
    preserve_format: true  # Don't restructure, just enhance
    
  Root Cause Analysis:
    goal: "Deep technical dive - this is the main section for engineers"
    emphasize: ["code paths", "config issues", "dependency failures"]
    expand: true  # Allow this section to use more word budget
    
  Impact Assessment:
    goal: "Translate business metrics to engineering terms"
    emphasize: ["requests failed", "latency p99", "error rates"]
    de_emphasize: ["revenue", "customer complaints"]
    
  Action Items:
    goal: "Technical tasks with specific owners"
    emphasize: ["monitoring", "testing", "code changes"]
    format: "checkbox list with owner and date"
```

---

## Key Code Components

### 1. Unified Extraction Module

```python
# src/livedoc/stages/extract.py - Unified content detection + extraction

import json
import ollama
from pathlib import Path

# Single prompt that detects content types AND extracts appropriately
UNIFIED_EXTRACTION_PROMPT = """Analyze this document page. First identify what content types exist, then extract each appropriately.

{context_hint}

Return JSON:
{
  "content_types": ["table", "chart", "graph", "image", "paragraph"],

  "tables": [{
    "headers": ["col1", "col2"],
    "rows": [["val1", "val2"]],
    "summary": "What this table shows",
    "importance": 1-3
  }],

  "visuals": [{
    "type": "chart|graph|image|diagram",
    "description": "What it shows",
    "data_points": ["key values/labels visible"],
    "trend": "increasing|decreasing|stable|comparison|n/a",
    "importance": 1-3
  }],

  "events": [{
    "date": "YYYY-MM-DD or null",
    "type": "incident|decision|action|other",
    "summary": "<30 words",
    "actors": ["names"],
    "importance": 1-3
  }],

  "entities": ["names, systems, orgs"],
  "dates": ["all dates found"],
  "facts": [{"text": "<25 words", "importance": 1-3}],

  "continues_previous": false,
  "continues_next": false
}

RULES:
- List ALL content types present on the page
- For TABLES: Extract headers and key rows (max 10 rows)
- For CHARTS/GRAPHS: Describe trend, extract visible data points
- For IMAGES/DIAGRAMS: Describe what's shown, extract any labels
- For PARAGRAPHS: Extract events with dates, actors, importance
- Importance: 3=critical (dates, decisions), 2=high, 1=supporting
- Preserve exact names, dates, numbers
- Empty arrays if content type not present"""

# Context hint for cross-page continuity
CONTEXT_HINT_TEMPLATE = """Previous page context: Topics: {topics}. Key actors: {actors}.
Check if this page continues from previous."""

def extract_page(image_path: Path, context_hint: str = "", model: str = "ministral-3-14b") -> dict:
    """Extract structured information using unified detect + extract approach."""

    prompt = UNIFIED_EXTRACTION_PROMPT.format(context_hint=context_hint)

    response = ollama.chat(
        model=model,
        messages=[{
            "role": "user",
            "content": prompt,
            "images": [str(image_path)]
        }],
        format="json"
    )

    return json.loads(response["message"]["content"])
```

### Content Type Handling

| Content Type | Extraction Strategy | Output Fields |
|--------------|---------------------|---------------|
| **Tables** | Headers + rows + summary | `tables[].headers, rows, summary, importance` |
| **Charts** | Description + data points + trend | `visuals[].description, data_points, trend` |
| **Graphs** | Same as charts | `visuals[].description, data_points, trend` |
| **Images/Diagrams** | Description + labels | `visuals[].description, data_points` |
| **Paragraphs** | Events + facts + entities | `events[], facts[], entities[]` |

### 2. Finalize Stage (New Architecture)

```python
# src/livedoc/stages/finalize.py - Importance-grouped synthesis

from typing import List, Dict, Any, Tuple

# Importance-grouped finalize prompt
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
- Use ONLY the information above - never add external knowledge
- Preserve all dates, names, figures exactly as given
- Write clear professional prose
- Target: {target_words} words

Write the report:"""


class FinalizeStage:
    """Synthesizes extractions directly into final report with importance grouping."""

    def _consolidate_extractions(self, extractions: List[Dict]) -> Tuple[List, List, List, List, List]:
        """Group all content by importance level."""
        critical, high, medium = [], [], []
        tables, visuals = [], []

        for ext in extractions:
            # Process events by importance (3=critical, 2=high, 1=medium)
            for event in ext.get("events", []):
                importance = event.get("importance", 2)
                formatted = self._format_event(event)
                if importance >= 3:
                    critical.append(formatted)
                elif importance >= 2:
                    high.append(formatted)
                else:
                    medium.append(formatted)

            # Process tables with summaries
            for table in ext.get("tables", []):
                tables.append(self._format_table(table))

            # Process visuals (charts, graphs, images)
            for visual in ext.get("visuals", []):
                visuals.append(self._format_visual(visual))

            # Process facts by importance
            for fact in ext.get("facts", []):
                importance = fact.get("importance", 1)
                text = fact.get("text", "")
                if importance >= 3:
                    critical.append(text)
                elif importance >= 2:
                    high.append(text)
                else:
                    medium.append(text)

        return critical, high, medium, tables, visuals

    def _format_table(self, table: dict) -> str:
        headers = table.get("headers", [])
        summary = table.get("summary", "")
        return f"Table ({', '.join(headers[:4])}): {summary}"

    def _format_visual(self, visual: dict) -> str:
        vtype = visual.get("type", "visual")
        desc = visual.get("description", "")
        trend = visual.get("trend", "")
        trend_str = f" - Trend: {trend}" if trend and trend != "n/a" else ""
        return f"{vtype.title()}: {desc}{trend_str}"
```

### 3. LiveDoc Manager (Legacy - Simplified Decision Output)

```python
# src/livedoc/stages/integrate.py - Sequential document builder with regex-parsed decisions

import re
import ollama
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class Decision:
    action: str      # ADD, UPDATE, SKIP
    topic: str       # What this is about
    section: str     # Target section name
    
def parse_decision(response: str) -> Optional[Decision]:
    """Parse plain-text decision using regex. No JSON parsing."""
    
    # Expected format: "action: ADD, topic: server outage, section: Timeline"
    pattern = r'action:\s*(ADD|UPDATE|SKIP)\s*,\s*topic:\s*([^,]+)\s*,\s*section:\s*(.+)'
    match = re.search(pattern, response, re.IGNORECASE)
    
    if match:
        return Decision(
            action=match.group(1).upper().strip(),
            topic=match.group(2).strip(),
            section=match.group(3).strip()
        )
    
    # Fallback: try to extract just the action
    action_match = re.search(r'action:\s*(ADD|UPDATE|SKIP)', response, re.IGNORECASE)
    if action_match:
        return Decision(
            action=action_match.group(1).upper().strip(),
            topic="unknown",
            section="Timeline"  # Default section
        )
    
    return None  # Parsing failed, will default to SKIP


class LiveDoc:
    def __init__(self, format_spec: dict, max_words: int):
        self.max_words = max_words
        self.format_spec = format_spec
        self.sections = {s: [] for s in format_spec["sections"]}
        self.tracked_dates = set()
        self.tracked_entities = set()
        
    def current_word_count(self) -> int:
        return sum(
            len(" ".join(items).split()) 
            for items in self.sections.values()
        )
    
    def needs_compression(self) -> bool:
        return self.current_word_count() > (self.max_words * 0.85)
    
    def _estimate_prompt_tokens(self, page_summary: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        livedoc_text = self._serialize_current_state()
        total_chars = len(livedoc_text) + len(page_summary) + 500  # 500 for prompt template
        return total_chars // 4
    
    def _get_compact_state(self) -> str:
        """Return minimal state representation for decision prompt."""
        lines = []
        for section, items in self.sections.items():
            if items:
                # Only show first line of each item to save tokens
                previews = [item.split('.')[0][:80] for item in items[:5]]
                lines.append(f"[{section}]: {len(items)} items - {', '.join(previews)}")
        return "\n".join(lines) if lines else "(empty document)"
    
    def process_page(self, page_data: dict, model: str) -> str:
        """Process one page extraction, return action taken."""
        
        # Create compact summary of page data for decision
        page_summary = self._summarize_page_for_decision(page_data)
        
        # Check token budget - keep decision prompt small
        if self._estimate_prompt_tokens(page_summary) > 2000:
            page_summary = page_summary[:1500] + "..."
        
        decision_prompt = f"""New information extracted from document page:
---
{page_summary}
---

Current report sections:
{self._get_compact_state()}

Available sections: {list(self.sections.keys())}

What should I do with this new information?
Reply with EXACTLY this format on one line:
action: [ADD/UPDATE/SKIP], topic: [brief topic], section: [section name]

- ADD = new information not in report
- UPDATE = extends or corrects existing entry  
- SKIP = redundant or not relevant"""

        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": decision_prompt}]
        )
        
        response_text = response["message"]["content"]
        decision = parse_decision(response_text)
        
        if decision is None:
            print(f"Warning: Could not parse decision, skipping. Response: {response_text[:100]}")
            return "SKIP"
        
        # Apply the decision
        if decision.action == "ADD":
            self._add_content(page_data, decision.section, decision.topic)
        elif decision.action == "UPDATE":
            self._update_content(page_data, decision.section, decision.topic)
        # SKIP does nothing
        
        # Track dates and entities from this page
        self._track_protected_items(page_data)
        
        # Check if compression needed after applying
        if self.needs_compression():
            self._compress(model)
            
        return decision.action
    
    def _summarize_page_for_decision(self, page_data: dict) -> str:
        """Create text summary of page JSON for decision prompt."""
        parts = []
        
        if page_data.get("events"):
            events = page_data["events"][:3]  # Limit to 3 events
            for e in events:
                parts.append(f"- Event ({e.get('date', 'no date')}): {e.get('summary', '')[:100]}")
        
        if page_data.get("topics"):
            parts.append(f"- Topics: {', '.join(page_data['topics'][:5])}")
            
        if page_data.get("key_facts"):
            parts.append(f"- Facts: {'; '.join(page_data['key_facts'][:3])}")
            
        return "\n".join(parts) if parts else "No significant content extracted"
    
    def _track_protected_items(self, page_data: dict):
        """Track dates and entities that must survive compression."""
        for event in page_data.get("events", []):
            if event.get("date"):
                self.tracked_dates.add(event["date"])
            for actor in event.get("actors", []):
                self.tracked_entities.add(actor)
        
        for entity in page_data.get("entities", []):
            self.tracked_entities.add(entity)
        
        for date in page_data.get("dates_mentioned", []):
            self.tracked_dates.add(date)
```

### 4. Smart Compression (Legacy - Token-Aware, Chunked)

```python
# src/livedoc/stages/compress.py - Intelligent word limit management

import re
from typing import List, Set
from dataclasses import dataclass

@dataclass
class CompressionConfig:
    target_reduction: float = 0.30      # Aim for 30% reduction
    min_words_per_item: int = 8         # Don't compress below this
    max_prompt_tokens: int = 1500       # Keep compression prompts small
    chunk_size: int = 5                 # Process N items at a time
    
class SmartCompressor:
    """
    Compression strategy:
    1. Identify protected content (dates, entities, topics)
    2. Calculate compression budget per section
    3. Process in small chunks to stay within token limits
    4. Validate protected items survived
    """
    
    def __init__(self, config: CompressionConfig = None):
        self.config = config or CompressionConfig()
        
    def compress_section(
        self, 
        items: List[str], 
        protected_dates: Set[str],
        protected_entities: Set[str],
        protected_topics: Set[str],
        model: str
    ) -> List[str]:
        """Compress a section while preserving protected content."""
        
        if len(items) <= 2:
            return items  # Too few items to compress meaningfully
        
        # Calculate target
        current_words = sum(len(item.split()) for item in items)
        target_words = int(current_words * (1 - self.config.target_reduction))
        
        # Build protected terms list (for prompt)
        protected_terms = self._build_protected_list(
            protected_dates, protected_entities, protected_topics
        )
        
        # Process in chunks to manage token budget
        compressed_items = []
        for i in range(0, len(items), self.config.chunk_size):
            chunk = items[i:i + self.config.chunk_size]
            
            # Check if chunk even needs compression
            chunk_words = sum(len(item.split()) for item in chunk)
            if chunk_words < 50:
                compressed_items.extend(chunk)
                continue
            
            compressed_chunk = self._compress_chunk(
                chunk, protected_terms, target_words, model
            )
            compressed_items.extend(compressed_chunk)
        
        # Validation pass
        self._validate_protected_items(
            compressed_items, protected_dates, protected_entities
        )
        
        return compressed_items
    
    def _build_protected_list(
        self, 
        dates: Set[str], 
        entities: Set[str], 
        topics: Set[str]
    ) -> str:
        """Create compact protected items reference for prompt."""
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
        target_words: int,
        model: str
    ) -> List[str]:
        """Compress a small chunk of items."""
        
        chunk_text = "\n".join(f"- {item}" for item in chunk)
        
        # Estimate if we're within token budget
        prompt_estimate = len(chunk_text) + len(protected_terms) + 600
        if prompt_estimate > self.config.max_prompt_tokens * 4:  # chars to tokens
            # Chunk too big, split further
            mid = len(chunk) // 2
            left = self._compress_chunk(chunk[:mid], protected_terms, target_words, model)
            right = self._compress_chunk(chunk[mid:], protected_terms, target_words, model)
            return left + right
        
        compress_prompt = f"""Compress these report items while keeping all protected terms.

ITEMS TO COMPRESS:
{chunk_text}

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

        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": compress_prompt}]
        )
        
        # Parse response - extract lines starting with dash
        response_text = response["message"]["content"]
        compressed = []
        for line in response_text.split("\n"):
            line = line.strip()
            if line.startswith("-"):
                item = line[1:].strip()
                if item and len(item.split()) >= self.config.min_words_per_item:
                    compressed.append(item)
        
        # Fallback if parsing failed
        if not compressed:
            return chunk
            
        return compressed
    
    def _validate_protected_items(
        self,
        compressed: List[str],
        dates: Set[str],
        entities: Set[str]
    ) -> None:
        """Verify critical items survived compression."""
        
        full_text = " ".join(compressed).lower()
        
        missing_dates = []
        for date in dates:
            # Normalize date formats for comparison
            if date.lower() not in full_text and date.replace("-", "/") not in full_text:
                missing_dates.append(date)
        
        missing_entities = []
        for entity in entities:
            if entity.lower() not in full_text:
                missing_entities.append(entity)
        
        if missing_dates:
            print(f"WARNING: Compression lost dates: {missing_dates}")
            # Could raise exception or trigger re-compression
            
        if missing_entities and len(missing_entities) > len(entities) * 0.2:
            print(f"WARNING: Compression lost >20% of entities: {missing_entities[:5]}")


def calculate_section_budgets(
    sections: dict, 
    max_words: int, 
    format_spec: dict
) -> dict:
    """Allocate word budget per section based on priority."""
    
    # Default weights (can be overridden in format_spec)
    default_weights = {
        "Executive Summary": 0.10,
        "Timeline": 0.35,
        "Root Cause Analysis": 0.25,
        "Impact Assessment": 0.15,
        "Action Items": 0.15
    }
    
    weights = format_spec.get("section_weights", default_weights)
    
    budgets = {}
    for section in sections.keys():
        weight = weights.get(section, 0.10)  # Default 10% for unknown sections
        budgets[section] = int(max_words * weight)
    
    return budgets
```

### 5. Perspective Rewriter (Dual Mode)

```python
# src/livedoc/stages/perspective.py - Section-level and global perspective rewriting

import yaml
import ollama
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

@dataclass
class SectionGoal:
    goal: str
    emphasize: list
    de_emphasize: list = None
    max_words: int = None
    preserve_format: bool = False
    expand: bool = False


class PerspectiveRewriter:
    """
    Two modes:
    - Mode A (section-level): Per-section goals, model generates tailored prompts
    - Mode B (global): Single perspective applied to entire document
    """
    
    def __init__(self, model: str):
        self.model = model
    
    # =========================================================================
    # MODE A: Section-Level Perspective
    # =========================================================================
    
    def rewrite_by_sections(
        self, 
        livedoc: 'LiveDoc', 
        config_path: Path
    ) -> str:
        """Mode A: Apply per-section perspective goals."""
        
        config = yaml.safe_load(config_path.read_text())
        meta = config.get("meta", {})
        section_configs = config.get("sections", {})
        
        rewritten_sections = {}
        
        for section_name, content_items in livedoc.sections.items():
            if not content_items:
                rewritten_sections[section_name] = []
                continue
                
            section_config = section_configs.get(section_name, {})
            
            if section_config:
                # Generate tailored prompt for this section
                tailored_prompt = self._generate_section_prompt(
                    section_name, 
                    section_config, 
                    meta
                )
                
                # Rewrite with generated prompt
                rewritten = self._rewrite_section(
                    section_name,
                    content_items,
                    tailored_prompt,
                    section_config.get("max_words"),
                    section_config.get("preserve_format", False)
                )
            else:
                # No specific config, apply only meta voice
                rewritten = self._rewrite_section_basic(
                    section_name, content_items, meta
                )
            
            rewritten_sections[section_name] = rewritten
        
        return self._render_final_document(rewritten_sections, livedoc.format_spec)
    
    def _generate_section_prompt(
        self, 
        section_name: str, 
        section_config: dict,
        meta: dict
    ) -> str:
        """Model generates an optimized rewrite prompt based on user's goal."""
        
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

        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": meta_prompt}]
        )
        
        return response["message"]["content"]
    
    def _rewrite_section(
        self,
        section_name: str,
        content_items: list,
        tailored_prompt: str,
        max_words: Optional[int],
        preserve_format: bool
    ) -> list:
        """Apply tailored prompt to rewrite a section."""
        
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

        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": rewrite_prompt}]
        )
        
        # Parse list output
        result = []
        for line in response["message"]["content"].split("\n"):
            line = line.strip()
            if line.startswith("-"):
                result.append(line[1:].strip())
        
        return result if result else content_items
    
    # =========================================================================
    # MODE B: Global Perspective  
    # =========================================================================
    
    def rewrite_global(
        self, 
        livedoc: 'LiveDoc', 
        perspective_path: Path
    ) -> str:
        """Mode B: Apply single perspective to entire document."""
        
        perspective_config = perspective_path.read_text()
        
        # Render current document
        current_doc = self._render_final_document(
            livedoc.sections, 
            livedoc.format_spec
        )
        
        # Check token budget - trim if needed
        if len(current_doc) > 6000:  # ~1500 tokens
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
- Stay within {livedoc.max_words} words total

Write the complete rewritten report in markdown format."""

        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": rewrite_prompt}]
        )
        
        return response["message"]["content"]
    
    def _render_final_document(self, sections: dict, format_spec: dict) -> str:
        """Render sections into final markdown document."""
        
        lines = [f"# {format_spec.get('title', 'Report')}\n"]
        
        for section_name in format_spec.get("section_order", sections.keys()):
            if section_name in sections and sections[section_name]:
                lines.append(f"## {section_name}\n")
                for item in sections[section_name]:
                    lines.append(f"- {item}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _trim_for_rewrite(self, doc: str, max_chars: int) -> str:
        """Trim document while keeping structure."""
        if len(doc) <= max_chars:
            return doc
        
        # Keep first and last portions
        keep_start = int(max_chars * 0.6)
        keep_end = int(max_chars * 0.3)
        
        return doc[:keep_start] + "\n\n[... content trimmed ...]\n\n" + doc[-keep_end:]
```

### 6. CLI Entry Point

```python
# src/livedoc/cli.py - Command line interface

import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="Generate reports from document collections"
    )
    parser.add_argument("input_dir", type=Path, help="Directory with PDFs")
    parser.add_argument("--format", type=Path, required=True,
                        help="Path to format.md specification")
    parser.add_argument("--output", type=Path, default=Path("./output"),
                        help="Output directory")
    parser.add_argument("--max-words", type=int, default=1500,
                        help="Maximum words in final report")
    
    # Perspective options (mutually exclusive)
    perspective_group = parser.add_mutually_exclusive_group()
    perspective_group.add_argument(
        "--perspective", type=str, default=None,
        help="Mode B: Global perspective name (loads perspectives/{name}.md)"
    )
    perspective_group.add_argument(
        "--perspective-sections", type=Path, default=None,
        help="Mode A: Section-level perspective (path to YAML config)"
    )
    
    parser.add_argument("--model", type=str, default="ministral-3-14b",
                        help="Ollama model to use")
    parser.add_argument("--dpi", type=int, default=150,
                        help="Image conversion DPI")
    parser.add_argument("--debug", action="store_true",
                        help="Save intermediate extraction JSONs")
    
    args = parser.parse_args()
    
    # Pipeline execution
    pipeline = ReportPipeline(
        input_dir=args.input_dir,
        format_spec=args.format,
        output_dir=args.output,
        max_words=args.max_words,
        model=args.model,
        dpi=args.dpi,
        debug=args.debug
    )
    
    pipeline.run()
    
    # Apply perspective if requested
    if args.perspective:
        # Mode B: Global perspective
        perspective_path = args.input_dir / "perspectives" / f"{args.perspective}.md"
        pipeline.apply_global_perspective(perspective_path)
        
    elif args.perspective_sections:
        # Mode A: Section-level perspective
        pipeline.apply_section_perspective(args.perspective_sections)

if __name__ == "__main__":
    main()
```

**Usage Examples:**

```bash
# Basic report generation
python -m livedoc ./documents --format ./format.md --max-words 1500

# Mode B: Global engineering perspective
python -m livedoc ./documents --format ./format.md --perspective engineering

# Mode A: Section-level perspective control
python -m livedoc ./documents --format ./format.md \
  --perspective-sections ./perspectives/engineering_sections.yaml

# With debug output (saves extraction JSONs)
python -m livedoc ./documents --format ./format.md --debug
```
```

---

## Prerequisites & Setup

### System Requirements

- **Python**: 3.10 or higher
- **Ollama**: Latest version installed and running
- **Poppler**: Required for PDF to image conversion
- **Disk Space**: ~500MB for model + temporary image files

### Installation

1. **Install Ollama** (if not already installed):
   ```bash
   # macOS
   brew install ollama

   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Pull the required model**:
   ```bash
   ollama pull ministral-3-14b
   # Or alternative vision models:
   ollama pull llama3.2-vision:11b
   ```

3. **Install Poppler for PDF conversion**:
   ```bash
   # macOS
   brew install poppler

   # Ubuntu/Debian
   sudo apt-get install poppler-utils

   # Windows (via chocolatey)
   choco install poppler
   ```

4. **Install the package**:
   ```bash
   # Install in development mode (recommended)
   pip install -e .

   # Or install dependencies only
   pip install -r requirements.txt
   ```

5. **Verify Ollama is running**:
   ```bash
   ollama list  # Should show your downloaded models
   ```

### Directory Setup

Create the expected input structure before running:

```bash
mkdir -p input/documents input/perspectives output
```

Place your PDFs in `input/documents/` and create your `format.md` specification.

---

## Usage Examples

### Basic Report Generation

Generate a report from all PDFs in a directory with default settings:

```bash
python -m livedoc ./documents \
  --format ./format.md \
  --max-words 1500 \
  --output ./output
```

**What this does:**
- Converts all PDFs in `./documents` to images at 150 DPI
- Extracts structured information from each page using vision model
- Builds a LiveDoc by processing pages sequentially
- Outputs `report.md` to the specified output directory

### Mode B: Global Engineering Perspective

Apply a unified engineering voice across the entire report:

```bash
python -m livedoc ./documents \
  --format ./format.md \
  --max-words 1500 \
  --perspective engineering \
  --output ./output
```

**When to use Mode B:**
- You want consistent tone/voice throughout
- The perspective applies equally to all sections
- You have a simple rewrite requirement

**Output:** Creates both `report.md` (original) and `report_engineering.md` (rewritten).

### Mode A: Section-Level Perspective Control

Apply different emphasis and goals to each section independently:

```bash
python -m livedoc ./documents \
  --format ./format.md \
  --max-words 1500 \
  --perspective-sections ./perspectives/engineering_sections.yaml \
  --output ./output
```

**When to use Mode A:**
- Different sections need different treatment
- You want fine-grained control over emphasis
- Some sections should expand while others compress

**Example:** Timeline keeps all dates but Root Cause Analysis gets expanded with technical details.

### Using Different Model

Switch to an alternative vision-capable model:

```bash
python -m livedoc ./documents \
  --format ./format.md \
  --model llama3.2-vision:11b \
  --output ./output
```

**Model selection tips:**
- `ministral-3-14b`: Best balance of quality and speed (recommended)
- `llama3.2-vision:11b`: Smaller, faster, but less accurate
- Larger models (32B+) may exceed VRAM on most GPUs

### Debug Mode (Saves Extraction JSONs)

Preserve intermediate extraction results for troubleshooting:

```bash
python -m livedoc ./documents \
  --format ./format.md \
  --debug \
  --output ./output
```

**Debug output includes:**
- `output/extraction/doc_001_page_001.json` - Raw extraction per page
- `output/extraction/decisions.log` - ADD/UPDATE/SKIP decisions
- `output/extraction/compression.log` - Compression operations

### Processing Large Document Sets

For collections with many PDFs (50+ pages total):

```bash
python -m livedoc ./documents \
  --format ./format.md \
  --max-words 2000 \
  --dpi 100 \
  --output ./output
```

**Tips for large sets:**
- Increase `--max-words` to capture more detail
- Lower `--dpi` (100 instead of 150) to reduce token cost per page
- Use `--debug` on first run to verify extraction quality

---

## Best Practices

### Document Preparation

1. **Organize input PDFs logically**: Name files with prefixes to control processing order (e.g., `01_incident_report.pdf`, `02_email_thread.pdf`)

2. **Remove irrelevant pages**: Pre-filter PDFs to exclude cover pages, blank pages, or appendices that don't contain useful information

3. **Ensure readable quality**: Scanned documents should be at least 150 DPI; blurry or low-contrast pages will produce poor extractions

### Format Specification

1. **Be explicit about section structure**: The model follows your `format.md` closely—include all sections you want in the output

2. **Set appropriate word limits per section**: Use `section_weights` in format spec to allocate budget where it matters most

3. **Include example entries**: Adding 1-2 example entries in format.md helps the model understand expected style

### Perspective Configuration

1. **Start with Mode B (global)**: Test with a simple global perspective before creating complex section-level configs

2. **Use specific terminology lists**: In perspective configs, list exact terms to use/avoid rather than general guidance

3. **Test incrementally**: Run with `--debug` and inspect `decisions.log` to see how the model interprets your perspective

### Performance Optimization

1. **Batch similar documents**: Process related PDFs together so the LiveDoc can effectively deduplicate

2. **Tune compression thresholds**: If output is too sparse, increase `max_words`; if too verbose, lower it

3. **Monitor VRAM usage**: Run `nvidia-smi` in another terminal to ensure model fits in memory

### Quality Assurance

1. **Always use debug mode on first run**: Verify extractions look correct before processing full sets

2. **Check date preservation**: Dates are critical—compare output against source to ensure none were lost

3. **Validate entity names**: Named entities should appear exactly as in source documents

### Common Workflows

**Incident Post-Mortem:**
```bash
# 1. Process all incident-related docs
python -m livedoc ./incident_docs --format ./formats/postmortem.md --debug

# 2. Review debug output, adjust format if needed

# 3. Generate engineering-focused version
python -m livedoc ./incident_docs --format ./formats/postmortem.md \
  --perspective engineering
```

**Weekly Status Report:**
```bash
# Process week's communications with tight word limit
python -m livedoc ./weekly_docs --format ./formats/status.md \
  --max-words 800 --perspective-sections ./perspectives/exec_summary.yaml
```

**Multi-Team Report:**
```bash
# Generate base report then multiple perspectives
python -m livedoc ./project_docs --format ./formats/project.md

python -m livedoc ./project_docs --format ./formats/project.md \
  --perspective engineering

python -m livedoc ./project_docs --format ./formats/project.md \
  --perspective product
```

---

## Token Budget Management

A 14B model has limited context window (~8K tokens typically). Every prompt must stay within budget.

### Budget Allocation Per Step

| Step | Max Input Tokens | Strategy |
|------|------------------|----------|
| Step 2: Unified Extraction | ~450 | Image + unified prompt (single call) |
| Step 2: Context Hint | ~50 | Previous page reference (if applicable) |
| Step 3: Finalize | ~400-600 | Importance-grouped content |
| Step 3 (Legacy): Decision | ~1500 | Compact state + page summary |
| Step 3 (Legacy): Compression | ~1500 | Small chunks (5 items max) |
| Step 4: Rewrite | ~2500 | Full doc (already within word limit) |

**New Architecture Efficiency**: ~450 tokens/page (single call) vs ~550 tokens (separate classify + extract).

### Safeguards in Code

```python
# Decision prompt - compact state representation
def _get_compact_state(self) -> str:
    """Show only section names + item count + first 80 chars of first 5 items."""
    # [Timeline]: 12 items - Server outage at 14:32, Response team assembled...
    
# Compression - chunk processing  
chunk_size: int = 5  # Process 5 items at a time max

# Rewrite - trim if needed
if len(current_doc) > 6000:  # ~1500 tokens
    current_doc = self._trim_for_rewrite(current_doc, 5000)

# Extraction - summary for decision (not full JSON)
def _summarize_page_for_decision(self, page_data: dict) -> str:
    """Convert JSON to compact text: 3 events, 5 topics, 3 facts max."""
```

### Why No JSON for Decisions?

1. **Smaller output**: `action: ADD, topic: outage, section: Timeline` is ~10 tokens
2. **Faster inference**: No need for structured generation
3. **More robust**: Regex handles minor formatting variations
4. **Fallback safe**: Unknown format → SKIP (safest default)

---

## Directory Structure

```
livedoc/
├── src/
│   └── livedoc/
│       ├── __init__.py
│       ├── __main__.py      # Entry point for python -m livedoc
│       ├── cli.py           # CLI argument parsing
│       ├── config/
│       │   └── settings.py  # Pipeline configuration
│       ├── core/
│       │   ├── context.py   # Processing context
│       │   ├── document.py  # Document representation
│       │   ├── extraction.py # Data structures for multi-content extraction
│       │   ├── pipeline.py  # Pipeline orchestration
│       │   └── stage.py     # Stage base class
│       ├── stages/
│       │   ├── convert.py   # PDF to image conversion
│       │   ├── extract.py   # Unified vision extraction (detect + extract)
│       │   ├── finalize.py  # Direct synthesis with importance grouping
│       │   ├── integrate.py # LiveDoc integration (legacy)
│       │   ├── compress.py  # Smart compression (legacy)
│       │   └── perspective.py # Perspective rewriting
│       ├── llm/
│       │   ├── client.py    # LLM client interface
│       │   └── ollama.py    # Ollama implementation
│       └── utils/
│           ├── checkpoint.py # Checkpoint/resume support
│           └── parsing.py   # Response parsing
├── tests/
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Prompts Reference

### Unified Extraction Prompt (JSON output - Step 2)

```
Analyze this document page. First identify what content types exist, then extract each appropriately.

{context_hint}

Return JSON:
{
  "content_types": ["table", "chart", "graph", "image", "paragraph"],

  "tables": [{
    "headers": ["col1", "col2"],
    "rows": [["val1", "val2"]],
    "summary": "What this table shows",
    "importance": 1-3
  }],

  "visuals": [{
    "type": "chart|graph|image|diagram",
    "description": "What it shows",
    "data_points": ["key values/labels visible"],
    "trend": "increasing|decreasing|stable|comparison|n/a",
    "importance": 1-3
  }],

  "events": [{
    "date": "YYYY-MM-DD or null",
    "type": "incident|decision|action|other",
    "summary": "<30 words",
    "actors": ["names"],
    "importance": 1-3
  }],

  "entities": ["names, systems, orgs"],
  "dates": ["all dates found"],
  "facts": [{"text": "<25 words", "importance": 1-3}],

  "continues_previous": false,
  "continues_next": false
}

RULES:
- List ALL content types present on the page
- For TABLES: Extract headers and key rows (max 10 rows)
- For CHARTS/GRAPHS: Describe trend, extract visible data points
- For IMAGES/DIAGRAMS: Describe what's shown, extract any labels
- For PARAGRAPHS: Extract events with dates, actors, importance
- Importance: 3=critical (dates, decisions), 2=high, 1=supporting
- Preserve exact names, dates, numbers
- Empty arrays if content type not present
- ONLY extract information EXPLICITLY visible - never infer or assume
```

**Context hint** (provided when previous page continues):
```
Previous page context: Topics: {topics}. Key actors: {actors}.
Check if this page continues from previous.
```

### LiveDoc Decision Prompt (Plain text output)

```
New information extracted from document page:
---
{page_summary}
---

Current report sections:
{compact_state}

Available sections: {section_list}

What should I do with this new information?
Reply with EXACTLY this format on one line:
action: [ADD/UPDATE/SKIP], topic: [brief topic], section: [section name]

- ADD = new information not in report
- UPDATE = extends or corrects existing entry  
- SKIP = redundant or not relevant
```

**Parsing with regex:**
```python
pattern = r'action:\s*(ADD|UPDATE|SKIP)\s*,\s*topic:\s*([^,]+)\s*,\s*section:\s*(.+)'
match = re.search(pattern, response, re.IGNORECASE)
```

### Compression Prompt (List output)

```
Compress these report items while keeping all protected terms.

ITEMS TO COMPRESS:
{chunk_text}

DATES (keep exactly): {dates}
NAMES (keep exactly): {entities}

COMPRESSION RULES:
1. NEVER change or remove dates - copy exactly as written
2. NEVER change entity/person names - copy exactly  
3. Merge items about the same event into one
4. Remove filler words (very, really, basically, etc.)
5. Keep technical terms and error codes
6. Each output item should be 8-25 words

Write compressed items as a simple list, one per line starting with dash:
- compressed item 1
- compressed item 2
```

### Section Prompt Generation (Mode A)

```
Create a rewrite prompt for the "{section_name}" section.

USER'S GOAL: {goal}
VOICE: {voice}
TERMINOLOGY: {terminology}

EMPHASIZE these aspects: {emphasize}
DE-EMPHASIZE these aspects: {de_emphasize}

Write a clear, direct prompt (3-5 sentences) that I'll use to rewrite the section.
The prompt should:
- Be specific about what to highlight
- Specify the tone/voice
- Give concrete guidance on what to change

Write only the prompt, nothing else.
```

### Global Perspective Rewrite (Mode B)

```
Rewrite this report from a specific perspective.

PERSPECTIVE GUIDE:
{perspective_md}

CURRENT REPORT:
{report_md}

RULES:
- Keep ALL dates exactly as written
- Keep ALL entity/person names exactly as written
- Adjust emphasis and framing per the perspective guide
- Match the voice and terminology specified
- Stay within {max_words} words total

Write the complete rewritten report in markdown format.
```

---

