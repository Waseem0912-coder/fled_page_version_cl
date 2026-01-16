"""Pipeline orchestrator for coordinating stages."""

from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from livedoc.core.stage import PipelineStage, StageError
from livedoc.core.context import PipelineContext
from livedoc.core.document import LiveDocument
from livedoc.config.settings import PipelineConfig
from livedoc.llm.client import LLMClient
from livedoc.llm.ollama import OllamaClient
from livedoc.utils.checkpoint import CheckpointManager
from livedoc.utils.parsing import parse_format_spec

if TYPE_CHECKING:
    from livedoc.stages.convert import ConvertStage
    from livedoc.stages.extract import ExtractStage
    from livedoc.stages.integrate import IntegrateStage
    from livedoc.stages.compress import CompressStage
    from livedoc.stages.perspective import PerspectiveStage


class Pipeline:
    """Orchestrates execution of pipeline stages.

    The Pipeline class manages the execution of a sequence of stages,
    handling checkpointing, error recovery, and stage dependencies.

    Example:
        from livedoc import Pipeline, PipelineConfig
        from livedoc.stages import ConvertStage, ExtractStage, IntegrateStage

        config = PipelineConfig(format_spec_path=Path("format.md"))
        pipeline = Pipeline(config=config)

        pipeline.add_stage(ConvertStage())
        pipeline.add_stage(ExtractStage())
        pipeline.add_stage(IntegrateStage())

        context = pipeline.run(input_dir=Path("./documents"))
    """

    def __init__(
        self,
        config: PipelineConfig,
        stages: Optional[List[PipelineStage]] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """Initialize the pipeline.

        Args:
            config: Pipeline configuration.
            stages: Optional list of stages to execute.
            llm_client: Optional LLM client (defaults to OllamaClient).
        """
        self.config = config
        self.stages: List[PipelineStage] = stages or []
        self.llm_client = llm_client or OllamaClient(model=config.model)

    def add_stage(self, stage: PipelineStage) -> "Pipeline":
        """Add a stage to the pipeline.

        Provides a fluent API for building pipelines.

        Args:
            stage: Stage to add.

        Returns:
            Self for chaining.
        """
        self.stages.append(stage)
        return self

    def run(
        self,
        input_dir: Path,
        output_dir: Optional[Path] = None,
        perspective_path: Optional[Path] = None,
        perspective_sections_path: Optional[Path] = None,
    ) -> PipelineContext:
        """Execute all pipeline stages.

        Args:
            input_dir: Directory containing input PDFs.
            output_dir: Optional output directory (defaults to ./output).
            perspective_path: Optional path to global perspective file.
            perspective_sections_path: Optional path to section perspective config.

        Returns:
            Final pipeline context after all stages.

        Raises:
            StageError: If a stage fails to execute.
        """
        output_dir = output_dir or Path("./output")

        print(f"Starting pipeline for {input_dir}")

        # Parse format specification
        format_spec = parse_format_spec(
            self.config.format_spec_path,
            self.config.max_words,
        )
        print(f"Loaded format spec: {format_spec.get('title', 'Untitled')}")

        # Create context
        context = PipelineContext(
            input_dir=input_dir,
            output_dir=output_dir,
            config=self.config,
            llm_client=self.llm_client,
            format_spec=format_spec,
            debug=self.config.debug,
            perspective_path=perspective_path,
            perspective_sections_path=perspective_sections_path,
        )

        # Check for checkpoint
        checkpoint_manager = CheckpointManager(output_dir)
        if self.config.resume and checkpoint_manager.exists():
            if checkpoint_manager.restore_context(context, LiveDocument):
                print(f"Resumed from checkpoint at page {context.last_processed_page}")

        # Execute stages
        for stage in self.stages:
            if stage.should_skip(context):
                print(f"Skipping stage: {stage.name}")
                continue

            try:
                context = stage.execute(context)
            except Exception as e:
                stage.on_error(context, e)
                if isinstance(e, StageError):
                    raise
                raise StageError(stage.name, str(e)) from e

        # Save output
        self._save_output(context)

        # Cleanup
        checkpoint_manager.cleanup()
        if not self.config.debug:
            checkpoint_manager.cleanup_images(context.image_dir)

        print(f"\nPipeline complete. Report saved to: {context.report_path}")

        return context

    def _save_output(self, context: PipelineContext) -> Path:
        """Save the final report.

        Args:
            context: Pipeline context with document.

        Returns:
            Path to saved report.
        """
        print("\n--- Saving output ---")

        context.output_dir.mkdir(parents=True, exist_ok=True)

        if context.document:
            report_content = context.document.to_markdown()
            context.report_path.write_text(report_content)

            print(f"  Report: {context.report_path}")
            print(f"  Word count: {context.document.current_word_count()}")

        return context.report_path

    @classmethod
    def create_default(cls, config: PipelineConfig) -> "Pipeline":
        """Create a pipeline with default stages.

        Creates a pipeline with the standard stages:
        Convert -> Extract -> Integrate -> Perspective

        Args:
            config: Pipeline configuration.

        Returns:
            Configured Pipeline instance.
        """
        from livedoc.stages.convert import ConvertStage
        from livedoc.stages.extract import ExtractStage
        from livedoc.stages.integrate import IntegrateStage
        from livedoc.stages.perspective import PerspectiveStage

        pipeline = cls(config=config)
        pipeline.add_stage(ConvertStage())
        pipeline.add_stage(ExtractStage())
        pipeline.add_stage(IntegrateStage())
        pipeline.add_stage(PerspectiveStage())

        return pipeline
