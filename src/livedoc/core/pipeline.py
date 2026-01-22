"""Pipeline orchestrator for coordinating stages."""

from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from livedoc.core.stage import PipelineStage, StageError
from livedoc.core.context import PipelineContext
from livedoc.core.document import LiveDocument
from livedoc.config.settings import PipelineConfig
from livedoc.llm.client import LLMClient
from livedoc.llm.ollama import OllamaClient
from livedoc.llm.vllm import VLLMClient
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
        vision_client: Optional[LLMClient] = None,
    ):
        """Initialize the pipeline.

        Args:
            config: Pipeline configuration.
            stages: Optional list of stages to execute.
            llm_client: Optional LLM client for text tasks (defaults to OllamaClient).
            vision_client: Optional LLM client for vision tasks (defaults to llm_client).
        """
        self.config = config
        self.stages: List[PipelineStage] = stages or []

        # Create text client (for text processing tasks)
        text_model = config.get_text_model()
        self.llm_client = llm_client or self._create_client(config, text_model)

        # Create vision client (for extraction tasks)
        vision_model = config.get_vision_model()
        if vision_client:
            self.vision_client = vision_client
        elif vision_model == text_model:
            # Share the same client if models are the same
            self.vision_client = self.llm_client
        else:
            # Create separate client for vision tasks
            self.vision_client = self._create_client(config, vision_model)

        # Log model configuration
        print(f"Using backend: {config.backend}")
        if config.backend == "vllm":
            print(f"  API URL: {config.api_base_url}")
        if vision_model != text_model:
            print(f"Using dual models: vision={vision_model}, text={text_model}")

    def _create_client(self, config: PipelineConfig, model: str) -> LLMClient:
        """Create an LLM client based on the configured backend.

        Args:
            config: Pipeline configuration.
            model: Model name to use.

        Returns:
            Configured LLM client instance.
        """
        if config.backend == "vllm":
            return VLLMClient(
                model=model,
                base_url=config.api_base_url,
                api_key=config.api_key,
            )
        else:
            # Default to Ollama
            return OllamaClient(model=model)

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

        # Create context with both text and vision clients
        context = PipelineContext(
            input_dir=input_dir,
            output_dir=output_dir,
            config=self.config,
            llm_client=self.llm_client,
            vision_client=self.vision_client,
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
            context: Pipeline context with document or final_report.

        Returns:
            Path to saved report.
        """
        print("\n--- Saving output ---")

        context.output_dir.mkdir(parents=True, exist_ok=True)

        # Prefer final_report from FinalizeStage if available
        if context.final_report:
            # Save as .txt for the new architecture (not structured markdown)
            report_path = context.output_dir / "report.txt"
            report_path.write_text(context.final_report)
            print(f"  Report: {report_path}")
            print(f"  Word count: {len(context.final_report.split())}")
            return report_path
        elif context.document:
            # Fallback to old markdown output
            report_content = context.document.to_markdown()
            context.report_path.write_text(report_content)
            print(f"  Report: {context.report_path}")
            print(f"  Word count: {context.document.current_word_count()}")

        return context.report_path

    @classmethod
    def create_default(cls, config: PipelineConfig) -> "Pipeline":
        """Create a pipeline with default stages.

        Creates a pipeline with the standard stages:
        - New architecture: Convert -> Extract -> Finalize (direct synthesis)
        - Legacy: Convert -> Extract -> Integrate -> Perspective

        Args:
            config: Pipeline configuration.

        Returns:
            Configured Pipeline instance.
        """
        from livedoc.stages.convert import ConvertStage
        from livedoc.stages.extract import ExtractStage

        pipeline = cls(config=config)
        pipeline.add_stage(ConvertStage())
        pipeline.add_stage(ExtractStage())

        if config.use_finalize_stage:
            # New architecture: direct synthesis from extractions
            from livedoc.stages.finalize import FinalizeStage
            pipeline.add_stage(FinalizeStage())
        else:
            # Legacy architecture: integrate -> compress -> perspective
            from livedoc.stages.integrate import IntegrateStage
            from livedoc.stages.perspective import PerspectiveStage
            pipeline.add_stage(IntegrateStage())
            pipeline.add_stage(PerspectiveStage())

        return pipeline
