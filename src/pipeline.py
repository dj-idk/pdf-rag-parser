"""
Main Pipeline Orchestrator
Coordinates all phases: Extraction → Cleaning → Chunking → File Organization
"""

import logging
from typing import Dict, Optional, Any
from pathlib import Path

from src.config import PipelineConfig
from src.phases.extraction import ExtractionPhase, ExtractionMetadata
from src.phases.cleaning import CleaningPhase, CleaningMetadata
from src.phases.chunking import ChunkingPhase, ChunkingMetadata
from src.phases.file_organization import FileOrganizationPhase, FileOrganizationMetadata

logger = logging.getLogger(__name__)


class PipelineResult:
    """Result of pipeline execution."""

    def __init__(
        self,
        extraction_metadata: ExtractionMetadata,
        cleaning_metadata: CleaningMetadata,
        chunking_metadata: ChunkingMetadata,
        organization_metadata: FileOrganizationMetadata,
    ):
        self.extraction = extraction_metadata
        self.cleaning = cleaning_metadata
        self.chunking = chunking_metadata
        self.organization = organization_metadata

    def summary(self) -> Dict[str, Any]:
        """Get summary of pipeline execution."""
        return {
            "extraction": {
                "total_pages": self.extraction.total_pages,
                "total_blocks": self.extraction.total_blocks,
                "total_characters": self.extraction.total_characters,
                "library": self.extraction.extraction_library,
            },
            "cleaning": {
                "blocks_input": self.cleaning.total_blocks_input,
                "blocks_output": self.cleaning.total_blocks_output,
                "blocks_removed": self.cleaning.blocks_removed,
                "characters_removed": self.cleaning.characters_removed,
            },
            "chunking": {
                "total_chunks": self.chunking.total_chunks,
                "total_characters": self.chunking.total_characters,
                "avg_chunk_size": self.chunking.avg_chunk_size,
                "min_chunk_size": self.chunking.min_chunk_size,
                "max_chunk_size": self.chunking.max_chunk_size,
            },
            "organization": {
                "chunks_saved": self.organization.total_chunks_saved,
                "total_chapters": self.organization.total_chapters,
                "total_parts": self.organization.total_parts,
                "index_file": self.organization.index_file_path,
            },
        }


class PDFRagPipeline:
    """Main pipeline for converting PDFs to RAG-ready chunks."""

    def __init__(self, config: PipelineConfig):
        """
        Initialize the pipeline.

        Args:
            config: PipelineConfig instance
        """
        self.config = config
        self.extraction_phase = ExtractionPhase(config.extraction.__dict__)
        self.cleaning_phase = CleaningPhase(config.cleaning.__dict__)
        self.chunking_phase = ChunkingPhase(config.chunking.__dict__)
        self.organization_phase = FileOrganizationPhase(config.output.__dict__)

        logger.info("Pipeline initialized")

    def run(self, pdf_path: str) -> PipelineResult:
        """
        Run the complete pipeline on a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            PipelineResult with metadata from all phases
        """
        logger.info("=" * 80)
        logger.info("Starting PDF RAG Pipeline")
        logger.info("=" * 80)

        # Phase 1: Extraction
        logger.info("\n[PHASE 1] Extraction")
        logger.info("-" * 80)
        text_blocks, extraction_metadata = self.extraction_phase.run(pdf_path)

        # Phase 2: Cleaning
        logger.info("\n[PHASE 2] Cleaning & Filtering")
        logger.info("-" * 80)
        cleaned_blocks, cleaning_metadata = self.cleaning_phase.run(text_blocks)

        # Phase 3: Chunking
        logger.info("\n[PHASE 3] Smart Chunking")
        logger.info("-" * 80)
        chunks, chunking_metadata = self.chunking_phase.run(
            cleaned_blocks, chapters_config=self.config.chapters
        )

        # Phase 4: File Organization
        logger.info("\n[PHASE 4] File Organization")
        logger.info("-" * 80)
        output_dir = self.config.output.output_dir
        organization_metadata = self.organization_phase.run(
            chunks, output_dir, chapters_config=self.config.chapters
        )

        # Create result
        result = PipelineResult(
            extraction_metadata=extraction_metadata,
            cleaning_metadata=cleaning_metadata,
            chunking_metadata=chunking_metadata,
            organization_metadata=organization_metadata,
        )

        # Log summary
        logger.info("\n" + "=" * 80)
        logger.info("Pipeline Complete - Summary")
        logger.info("=" * 80)
        summary = result.summary()
        for phase, metrics in summary.items():
            logger.info(f"\n{phase.upper()}:")
            for key, value in metrics.items():
                logger.info(f"  {key}: {value}")

        logger.info("\n" + "=" * 80)

        return result

    def save_reports(self, output_dir: str) -> None:
        """
        Save detailed reports from all phases.

        Args:
            output_dir: Directory to save reports
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving reports to: {output_dir}")

        # Note: Reports would be saved here if we had metadata instances
        # This is a placeholder for future enhancement
