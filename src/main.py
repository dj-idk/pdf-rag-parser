"""
Main entry point for the PDF RAG Parser.
"""

import logging
import argparse
from pathlib import Path

from src.config import PipelineConfig
from src.pipeline import PDFRagPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert PDF documents into RAG-ready semantic chunks"
    )
    parser.add_argument(
        "--input", type=str, required=True, help="Path to input PDF file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output/",
        help="Output directory (default: output/)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to configuration file (default: config.json)",
    )

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    if not input_path.suffix.lower() == ".pdf":
        logger.error(f"Input file must be a PDF: {args.input}")
        return 1

    # Load configuration
    try:
        config = PipelineConfig.from_json(args.config)
        config.output.output_dir = args.output
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {args.config}")
        return 1
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1

    # Run pipeline
    try:
        pipeline = PDFRagPipeline(config)
        result = pipeline.run(str(input_path))

        logger.info(f"\n✓ Pipeline completed successfully!")
        logger.info(f"Output saved to: {args.output}")

        return 0

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
