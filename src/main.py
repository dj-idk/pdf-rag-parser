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

        # TODO: Phase 3: Cleaning & Filtering
        logger.info("\n" + "=" * 60)
        logger.info("Phase 3: Cleaning & Filtering")
        logger.info("=" * 60)
        logger.info("(To be implemented)")

        # TODO: Phase 4: Smart Chunking
        logger.info("\n" + "=" * 60)
        logger.info("Phase 4: Smart Chunking")
        logger.info("=" * 60)
        logger.info("(To be implemented)")

        # TODO: Phase 5: File Organization
        logger.info("\n" + "=" * 60)
        logger.info("Phase 5: File Organization")
        logger.info("=" * 60)
        logger.info("(To be implemented)")

        logger.info("\n" + "=" * 60)
        logger.info("Pipeline Complete!")
        logger.info("=" * 60)
        logger.info(f"Output saved to: {output_path}")

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
