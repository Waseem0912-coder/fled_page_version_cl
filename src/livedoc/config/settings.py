"""Configuration dataclasses for the pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# Token budget for LLM calls - based on ~5K embedding length limit
# Reserve ~500 tokens for system instructions, ~500 for prompt template
# Leaves ~4000 tokens for actual content input
TOKEN_BUDGET_TOTAL = 5000
TOKEN_BUDGET_SYSTEM = 500
TOKEN_BUDGET_PROMPT = 500
TOKEN_BUDGET_CONTENT = 4000

# Approximate chars per token (conservative estimate)
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count from text.

    Args:
        text: Input text to estimate.

    Returns:
        Estimated token count.
    """
    return len(text) // CHARS_PER_TOKEN


def fits_token_budget(
    content: str,
    prompt_template: str = "",
    system_instructions: str = "",
    budget: int = TOKEN_BUDGET_TOTAL,
) -> bool:
    """Check if content fits within token budget.

    Args:
        content: Main content to check.
        prompt_template: Prompt template (optional).
        system_instructions: System instructions (optional).
        budget: Total token budget.

    Returns:
        True if total fits within budget.
    """
    total = estimate_tokens(content + prompt_template + system_instructions)
    return total < budget


@dataclass
class CompressionConfig:
    """Configuration for content compression behavior.

    Attributes:
        target_reduction: Target reduction ratio (0.30 = 30% reduction).
        min_words_per_item: Minimum words per item after compression.
        max_prompt_tokens: Maximum tokens for compression prompts.
        chunk_size: Number of items to process at a time.
    """

    target_reduction: float = 0.30
    min_words_per_item: int = 8
    max_prompt_tokens: int = 1500
    chunk_size: int = 5


@dataclass
class SectionGoal:
    """Configuration for rewriting a specific section.

    Attributes:
        goal: The rewriting goal/objective for this section.
        emphasize: List of aspects to emphasize.
        de_emphasize: List of aspects to de-emphasize.
        max_words: Optional word limit for the section.
        preserve_format: Whether to preserve the original structure.
        expand: Whether to expand content rather than compress.
    """

    goal: str
    emphasize: List[str] = field(default_factory=list)
    de_emphasize: List[str] = field(default_factory=list)
    max_words: Optional[int] = None
    preserve_format: bool = False
    expand: bool = False


@dataclass
class PerspectiveConfig:
    """Configuration for perspective rewriting.

    Attributes:
        voice: Writing voice (e.g., "Professional", "Technical", "Casual").
        terminology: Terminology style (e.g., "Standard", "Formal", "Simplified").
        sections: Per-section rewriting goals.
    """

    voice: str = "Professional"
    terminology: str = "Standard"
    sections: Dict[str, SectionGoal] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    """Main configuration for the pipeline.

    Attributes:
        format_spec_path: Path to format.md specification file (legacy).
        user_preferences_path: Path to user preferences txt file.
        max_words: Maximum words in final report.
        model: LLM model name (e.g., "ministral-3-14b"). Used as default for both vision and text.
        vision_model: LLM model for vision/extraction tasks. If None, uses 'model'.
        text_model: LLM model for text processing tasks. If None, uses 'model'.
        dpi: Image conversion DPI quality.
        debug: Whether to save debug artifacts.
        resume: Whether to resume from checkpoint.
        compression: Compression behavior configuration.
        compression_threshold: Word budget percentage that triggers compression.
        use_finalize_stage: Use new finalize stage instead of perspective stage.
    """

    format_spec_path: Optional[Path] = None
    user_preferences_path: Optional[Path] = None
    max_words: int = 1500
    model: str = "ministral-3-14b"
    vision_model: Optional[str] = None  # If None, uses 'model'
    text_model: Optional[str] = None    # If None, uses 'model'
    dpi: int = 150
    debug: bool = False
    resume: bool = False
    compression: CompressionConfig = field(default_factory=CompressionConfig)
    compression_threshold: float = 0.85
    use_finalize_stage: bool = True  # New architecture by default

    # Default sections if not specified in format.md
    default_sections: List[str] = field(default_factory=lambda: [
        "Executive Summary",
        "Timeline",
        "Root Cause Analysis",
        "Impact Assessment",
        "Action Items",
    ])

    # Section weight defaults for compression budgeting
    default_section_weights: Dict[str, float] = field(default_factory=lambda: {
        "Executive Summary": 0.10,
        "Timeline": 0.35,
        "Root Cause Analysis": 0.25,
        "Impact Assessment": 0.15,
        "Action Items": 0.15,
    })

    def get_vision_model(self) -> str:
        """Get the model to use for vision/extraction tasks.

        Returns:
            Vision model name, falling back to default model if not specified.
        """
        return self.vision_model or self.model

    def get_text_model(self) -> str:
        """Get the model to use for text processing tasks.

        Returns:
            Text model name, falling back to default model if not specified.
        """
        return self.text_model or self.model
