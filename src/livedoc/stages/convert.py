"""PDF to Image conversion stage."""

from pathlib import Path
from typing import List

from pdf2image import convert_from_path

from livedoc.core.stage import PipelineStage, StageError
from livedoc.core.context import PipelineContext


class ConvertStage(PipelineStage):
    """Pipeline stage that converts PDFs to images.

    Converts all PDF files in the input directory to PNG images
    for vision-based extraction.
    """

    @property
    def name(self) -> str:
        return "convert"

    def should_skip(self, context: PipelineContext) -> bool:
        """Skip if resuming and images already exist."""
        if context.resumed and context.image_dir.exists():
            image_paths = sorted(context.image_dir.glob("*.png"))
            if image_paths:
                return True
        return False

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Convert PDFs to images.

        Args:
            context: Pipeline context with input_dir and config.

        Returns:
            Updated context with image_paths populated.

        Raises:
            StageError: If no PDFs found or conversion fails.
        """
        print("\n--- Stage: Converting PDFs to images ---")

        # Check if we can reuse existing images
        if self.should_skip(context):
            context.image_paths = sorted(context.image_dir.glob("*.png"))
            print(f"Reusing {len(context.image_paths)} existing page images")
            return context

        # Fresh conversion
        context.image_dir.mkdir(parents=True, exist_ok=True)

        image_paths = self._convert_all_pdfs(
            input_dir=context.input_dir,
            output_dir=context.image_dir,
            dpi=context.config.dpi,
        )

        if not image_paths:
            raise StageError(
                self.name,
                f"No images generated from PDFs in {context.input_dir}",
            )

        context.image_paths = image_paths
        print(f"Total pages: {len(image_paths)}")

        return context

    def _convert_all_pdfs(
        self,
        input_dir: Path,
        output_dir: Path,
        dpi: int = 150,
    ) -> List[Path]:
        """Convert all PDFs in a directory to images.

        Args:
            input_dir: Directory containing PDF files.
            output_dir: Directory to save images.
            dpi: Image resolution (default 150).

        Returns:
            List of all generated image paths, sorted.
        """
        all_image_paths = []

        pdf_files = sorted(input_dir.glob("*.pdf"))

        if not pdf_files:
            print(f"Warning: No PDF files found in {input_dir}")
            return []

        for doc_index, pdf_path in enumerate(pdf_files, start=1):
            print(f"Converting {pdf_path.name} ({doc_index}/{len(pdf_files)})...")

            try:
                image_paths = self._convert_pdf_to_images(
                    pdf_path=pdf_path,
                    output_dir=output_dir,
                    dpi=dpi,
                    doc_index=doc_index,
                )
                all_image_paths.extend(image_paths)
                print(f"  Generated {len(image_paths)} page images")
            except Exception as e:
                print(f"  Error converting {pdf_path.name}: {e}")
                continue

        return sorted(all_image_paths)

    def _convert_pdf_to_images(
        self,
        pdf_path: Path,
        output_dir: Path,
        dpi: int = 150,
        doc_index: int = 1,
    ) -> List[Path]:
        """Convert a single PDF to images.

        Args:
            pdf_path: Path to the PDF file.
            output_dir: Directory to save images.
            dpi: Image resolution.
            doc_index: Document index for naming.

        Returns:
            List of paths to generated images.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Convert PDF to list of PIL images
        images = convert_from_path(str(pdf_path), dpi=dpi)

        image_paths = []
        for page_num, image in enumerate(images, start=1):
            # Generate filename: doc_001_page_001.png
            filename = f"doc_{doc_index:03d}_page_{page_num:03d}.png"
            image_path = output_dir / filename

            image.save(str(image_path), "PNG")
            image_paths.append(image_path)

        return image_paths
