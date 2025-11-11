"""
Main entry point for the PDF RAG Parser pipeline.
"""

import json
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional
from dataclasses import asdict

from src.config import ConfigManager
from src.phases.extraction import ExtractionPhase
from src.phases.structure import StructurePhase
from src.phases.cleaning import CleaningPhase
from src.phases.chunking import ChunkingPhase
from src.phases.file_organization import FileOrganizationPhase
from src.utils.validators import validate_pdf_path, validate_output_dir


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_argument_parser() -> argparse.ArgumentParser:
    """
    Set up command-line argument parser.

    Returns:
        ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Convert PDF documents into semantically chunked, RAG-ready text files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py --input book.pdf --
output output/
  python src/main.py --input book.pdf --output output/ --config config.json
  python src/main.py --input book.pdf --output output/ --verbose
        """,
    )

    parser.add_argument("--input", "-i", required=True, help="Path to input PDF file")

    parser.add_argument(
        "--output", "-o", default="output/", help="Output directory (default: output/)"
    )

    parser.add_argument(
        "--config", "-c", help="Path to configuration JSON file (optional)"
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    parser.add_argument(
        "--show-config", action="store_true", help="Show default configuration and exit"
    )

    return parser


def configure_logging(verbose: bool = False) -> None:
    """
    Configure logging level.

    Args:
        verbose: If True, set logging to DEBUG level
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    config_path: Optional[str] = (None,)


def run_pipeline(
    input_pdf: str,
    output_dir: str,
    config_path: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """
    Run the complete PDF RAG parser pipeline.

    Args:
        input_pdf: Path to input PDF file
        output_dir: Output directory
        config_path: Path to configuration file (optional)
        verbose: Enable verbose logging
    """
    configure_logging(verbose)

    logger.info("=" * 60)
    logger.info("PDF RAG Parser Pipeline")
    logger.info("=" * 60)

    # Validate inputs
    logger.info("Validating inputs...")
    validate_pdf_path(input_pdf)
    validate_output_dir(output_dir)

    # Load configuration
    logger.info("Loading configuration...")
    config = ConfigManager.load_config(config_path)

    # Get PDF filename without extension
    pdf_filename = Path(input_pdf).stem

    # Create output directory structure based on config
    if config.output.output_dir and config.output.output_dir != "output/":
        # Use custom output directory from config
        output_path = Path(config.output.output_dir)
    else:
        # Use default: output_dir/pdf_filename/
        output_path = Path(output_dir) / pdf_filename

    output_path.mkdir(parents=True, exist_ok=True)

    # Save configuration to output
    config_output_path = output_path / "config_used.json"
    ConfigManager.save_config(config, str(config_output_path))

    try:
        # Phase 1: Text Extraction
        logger.info("\n" + "=" * 60)
        logger.info("Phase 1: Text Extraction")
        logger.info("=" * 60)

        extraction_phase = ExtractionPhase(asdict(config.extraction))
        text_blocks, extraction_metadata = extraction_phase.run(input_pdf)

        # Save extraction report
        extraction_report_path = output_path / "extraction_report.json"
        extraction_phase.save_extraction_report(
            extraction_metadata, str(extraction_report_path)
        )

        logger.info(
            f"✓ Extraction complete: {extraction_metadata.total_blocks} blocks extracted"
        )
        logger.info(f"  Total characters: {extraction_metadata.total_characters}")
        logger.info(f"  Total pages: {extraction_metadata.total_pages}")

        # Phase 2: Structure Analysis
        logger.info("\n" + "=" * 60)
        logger.info("Phase 2: Structure Analysis")
        logger.info("=" * 60)

        structure_phase = StructurePhase(asdict(config.structure))
        structured_blocks, structure_metadata = structure_phase.run(
            text_blocks, extraction_metadata
        )

        # Save structure report
        structure_report_path = output_path / "structure_report.json"
        structure_phase.save_structure_report(
            structure_metadata, str(structure_report_path)
        )

        logger.info(
            f"✓ Structure analysis complete: {structure_metadata.classified_blocks} headings found"
        )
        logger.info(f"  Parts: {structure_metadata.parts_found}")
        logger.info(f"  Chapters: {structure_metadata.chapters_found}")
        logger.info(f"  Sections: {structure_metadata.sections_found}")
        logger.info(f"  Method: {structure_metadata.structure_method}")

        # Phase 3: Cleaning & Filtering
        logger.info("\n" + "=" * 60)
        logger.info("Phase 3: Cleaning & Filtering")
        logger.info("=" * 60)

        cleaning_phase = CleaningPhase(asdict(config.cleaning))
        cleaned_blocks, cleaning_metadata = cleaning_phase.run(
            structured_blocks, structure_metadata
        )

        # Save cleaning report
        cleaning_report_path = output_path / "cleaning_report.json"
        cleaning_phase.save_cleaning_report(
            cleaning_metadata, str(cleaning_report_path)
        )

        logger.info(
            f"✓ Cleaning complete: {cleaning_metadata['total_blocks_after']} blocks remaining"
        )
        logger.info(f"  Blocks removed: {cleaning_metadata['blocks_removed']}")
        logger.info(f"  Characters removed: {cleaning_metadata['characters_removed']}")

        # Phase 4: Smart Chunking
        logger.info("\n" + "=" * 60)
        logger.info("Phase 4: Smart Chunking")
        logger.info("=" * 60)

        # Convert StructuredTextBlock objects to dictionaries for chunking phase
        blocks_for_chunking = [
            {
                "content": block.content,
                "page_num": block.page_num,
                "chapter": block.parent_heading if block.hierarchy_level <= 1 else None,
                "section": block.parent_heading if block.hierarchy_level > 1 else None,
            }
            for block in cleaned_blocks
        ]

        chunking_phase = ChunkingPhase(asdict(config.chunking))
        chunks, chunking_metadata = chunking_phase.run(blocks_for_chunking)

        # Save chunking report
        chunking_report_path = output_path / "chunking_report.json"
        chunking_phase.save_chunking_report(
            chunking_metadata, str(chunking_report_path)
        )

        # Save chunks data
        chunks_data_path = output_path / "chunks.json"
        chunking_phase.save_chunks(chunks, str(chunks_data_path))

        logger.info(
            f"✓ Chunking complete: {chunking_metadata.total_chunks} chunks created"
        )
        logger.info(
            f"  Average chunk size: {chunking_metadata.avg_chunk_size:.0f} chars"
        )
        logger.info(f"  Min chunk size: {chunking_metadata.min_chunk_size} chars")
        logger.info(f"  Max chunk size: {chunking_metadata.max_chunk_size} chars")
        logger.info(f"  Split methods: {chunking_metadata.chunks_by_split_method}")

        # Phase 5: File Organization
        # Phase 5: File Organization
        logger.info("\n" + "=" * 60)
        logger.info("Phase 5: File Organization")
        logger.info("=" * 60)

        # Convert TextChunk objects to dictionaries for file organization phase
        chunks_for_org = [
            {
                "content": chunk.content,
                "chunk_id": chunk.chunk_id,
                "page_num": chunk.source_page,
                "part": "Uncategorized",  # Default part
                "chapter": chunk.source_chapter or "Uncategorized",
                "section": chunk.source_section or "Uncategorized",
                "char_count": chunk.char_count,
                "word_count": chunk.word_count,
                "sentence_count": chunk.sentence_count,
            }
            for chunk in chunks
        ]

        # Convert StructureMetadata to dictionary for file organization phase
        structure_metadata_dict = (
            asdict(structure_metadata) if structure_metadata else None
        )

        file_org_phase = FileOrganizationPhase(asdict(config.output))
        file_org_metadata = file_org_phase.run(
            chunks_for_org, str(output_path), structure_metadata_dict
        )

        # Save file organization report
        file_org_report_path = output_path / "file_organization_report.json"
        file_org_phase.save_file_organization_report(
            file_org_metadata, str(file_org_report_path)
        )

        logger.info(
            f"✓ File organization complete: {file_org_metadata.total_chunks_saved} chunks organized"
        )
        logger.info(f"  Parts: {file_org_metadata.total_parts}")
        logger.info(f"  Chapters: {file_org_metadata.total_chapters}")
        logger.info(f"  Index file: {file_org_metadata.index_file_path}")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=verbose)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    parser = setup_argument_parser()
    args = parser.parse_args()

    # Handle --show-config flag
    if args.show_config:
        print("Default Configuration:")
        print("=" * 60)
        print(ConfigManager.get_default_config_json())
        sys.exit(0)

    # Run pipeline
    run_pipeline(
        input_pdf=args.input,
        output_dir=args.output,
        config_path=args.config,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
