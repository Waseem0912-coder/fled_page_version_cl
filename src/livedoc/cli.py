"""CLI entry point for LiveDoc."""

import argparse
import sys
from pathlib import Path

from livedoc.core.pipeline import Pipeline
from livedoc.config.settings import PipelineConfig


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Generate reports from document collections using vision LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic report generation (new architecture - recommended)
  python -m livedoc ./documents --format ./format.md --max-words 1500

  # With custom user preferences
  python -m livedoc ./documents --format ./format.md --preferences ./user_preferences.txt

  # Legacy mode (old integrate->compress->perspective pipeline)
  python -m livedoc ./documents --format ./format.md --legacy

  # Mode B: Global engineering perspective (legacy)
  python -m livedoc ./documents --format ./format.md --perspective engineering --legacy

  # With debug output (saves extraction JSONs)
  python -m livedoc ./documents --format ./format.md --debug

  # Resume from checkpoint (for long documents)
  python -m livedoc ./documents --format ./format.md --resume
        """
    )

    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing PDF files to process"
    )

    parser.add_argument(
        "--format",
        type=Path,
        required=True,
        help="Path to format.md specification file"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output"),
        help="Output directory (default: ./output)"
    )

    parser.add_argument(
        "--max-words",
        type=int,
        default=1500,
        help="Maximum words in final report (default: 1500)"
    )

    # Perspective options (mutually exclusive)
    perspective_group = parser.add_mutually_exclusive_group()
    perspective_group.add_argument(
        "--perspective",
        type=str,
        default=None,
        metavar="NAME",
        help="Mode B: Global perspective name (loads perspectives/{name}.md from input_dir)"
    )
    perspective_group.add_argument(
        "--perspective-sections",
        type=Path,
        default=None,
        metavar="PATH",
        help="Mode A: Section-level perspective (path to YAML config)"
    )

    parser.add_argument(
        "--model",
        type=str,
        default="ministral-3-14b",
        help="Ollama model to use (default: ministral-3-14b)"
    )

    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Image conversion DPI (default: 150)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save intermediate extraction JSONs"
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint if available (for long documents)"
    )

    parser.add_argument(
        "--preferences",
        type=Path,
        default=None,
        help="Path to user preferences txt file (default: ./user_preferences.txt)"
    )

    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy architecture (integrate->compress->perspective) instead of direct synthesis"
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.input_dir.exists():
        print(f"Error: Input directory not found: {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.format.exists():
        print(f"Error: Format specification not found: {args.format}", file=sys.stderr)
        sys.exit(1)

    # Build perspective paths
    perspective_path = None
    perspective_sections_path = None

    if args.perspective:
        perspective_path = args.input_dir / "perspectives" / f"{args.perspective}.md"
        if not perspective_path.exists():
            print(f"Warning: Perspective file not found: {perspective_path}", file=sys.stderr)
            perspective_path = None

    if args.perspective_sections:
        perspective_sections_path = args.perspective_sections
        if not perspective_sections_path.exists():
            print(f"Warning: Section config not found: {perspective_sections_path}", file=sys.stderr)
            perspective_sections_path = None

    # Determine user preferences path
    user_preferences_path = args.preferences
    if not user_preferences_path:
        # Try default locations
        default_prefs = Path("./user_preferences.txt")
        if default_prefs.exists():
            user_preferences_path = default_prefs

    # Create configuration
    config = PipelineConfig(
        format_spec_path=args.format,
        user_preferences_path=user_preferences_path,
        max_words=args.max_words,
        model=args.model,
        dpi=args.dpi,
        debug=args.debug,
        resume=args.resume,
        use_finalize_stage=not args.legacy,
    )

    # Create and run pipeline
    try:
        pipeline = Pipeline.create_default(config)

        pipeline.run(
            input_dir=args.input_dir,
            output_dir=args.output,
            perspective_path=perspective_path,
            perspective_sections_path=perspective_sections_path,
        )

    except KeyboardInterrupt:
        print("\nPipeline interrupted by user", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
