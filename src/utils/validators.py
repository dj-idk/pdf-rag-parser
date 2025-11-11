"""
Input validation utilities.
"""

import logging
from pathlib import Path


logger = logging.getLogger(__name__)


def validate_pdf_path(pdf_path: str) -> None:
    """
    Validate that the PDF path exists and is a valid PDF file.

    Args:
        pdf_path: Path to PDF file

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not a PDF
    """
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {pdf_path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"File is not a PDF: {pdf_path}")

    logger.debug(f"PDF validation passed: {pdf_path}")


def validate_output_dir(output_dir: str) -> None:
    """
    Validate that the output directory path is valid.

    Args:
        output_dir: Path to output directory

    Raises:
        ValueError: If path is invalid
    """
    path = Path(output_dir)

    # Check if parent directory exists
    if not path.parent.exists():
        raise ValueError(f"Parent directory does not exist: {path.parent}")

    # Check if path exists and is not a directory
    if path.exists() and not path.is_dir():
        raise ValueError(f"Output path exists but is not a directory: {output_dir}")

    logger.debug(f"Output directory validation passed: {output_dir}")


def validate_config_path(config_path: str) -> None:
    """
    Validate that the config file path exists and is a JSON file.

    Args:
        config_path: Path to configuration file

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not a JSON file
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    if not path.is_file():
        raise ValueError(f"Config path is not a file: {config_path}")

    if path.suffix.lower() != ".json":
        raise ValueError(f"Config file must be JSON: {config_path}")

    logger.debug(f"Config validation passed: {config_path}")
