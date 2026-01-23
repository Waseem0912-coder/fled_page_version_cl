"""Utility functions and helpers."""

# Lazy imports to avoid circular dependencies
# Import these directly from their modules:
#   from livedoc.utils.checkpoint import CheckpointManager
#   from livedoc.utils.parsing import parse_decision, parse_format_spec

__all__ = ["CheckpointManager", "parse_decision", "parse_format_spec"]


def __getattr__(name: str):
    """Lazy import for backward compatibility."""
    if name == "CheckpointManager":
        from livedoc.utils.checkpoint import CheckpointManager
        return CheckpointManager
    if name == "parse_decision":
        from livedoc.utils.parsing import parse_decision
        return parse_decision
    if name == "parse_format_spec":
        from livedoc.utils.parsing import parse_format_spec
        return parse_format_spec
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
