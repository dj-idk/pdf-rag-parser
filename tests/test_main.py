"""
Tests for the main module.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.main import setup_argument_parser, configure_logging, run_pipeline


class TestArgumentParser:
    """Test command-line argument parser."""

    def test_parser_with_required_input(self):
        """Test parser with required input argument."""
        parser = setup_argument_parser()
        args = parser.parse_args(["--input", "test.pdf"])

        assert args.input == "test.pdf"
        assert args.output == "output/"
        assert args.config is None
        assert args.verbose is False

    def test_parser_with_all_arguments(self):
        """Test parser with all arguments."""
        parser = setup_argument_parser()
        args = parser.parse_args(
            [
                "--input",
                "test.pdf",
                "--output",
                "custom_output/",
                "--config",
                "config.json",
                "--verbose",
            ]
        )

        assert args.input == "test.pdf"
        assert args.output == "custom_output/"
        assert args.config == "config.json"
        assert args.verbose is True

    def test_parser_missing_required_input(self):
        """Test parser without required input argument."""
        parser = setup_argument_parser()

        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_parser_show_config_flag(self):
        """Test parser with show-config flag."""
        parser = setup_argument_parser()
        args = parser.parse_args(["--input", "test.pdf", "--show-config"])

        assert args.show_config is True


class TestConfigureLogging:
    """Test logging configuration."""

    def test_configure_logging_default(self):
        """Test default logging configuration."""
        configure_logging(verbose=False)
        # Should not raise

    def test_configure_logging_verbose(self):
        """Test verbose logging configuration."""
        configure_logging(verbose=True)
        # Should not raise


class TestRunPipeline:
    """Test pipeline execution."""

    @patch("src.main.ExtractionPhase")
    @patch("src.main.validate_pdf_path")
    @patch("src.main.validate_output_dir")
    def test_run_pipeline_success(
        self, mock_validate_output, mock_validate_pdf, mock_extraction
    ):
        """Test successful pipeline execution."""
        # Setup mocks
        mock_extraction_instance = MagicMock()
        mock_extraction.return_value = mock_extraction_instance

        mock_metadata = MagicMock()
        mock_metadata.total_blocks = 100
        mock_metadata.total_characters = 10000
        mock_metadata.total_pages = 10

        mock_extraction_instance.run.return_value = ([], mock_metadata)

        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                pdf_path = tmp_pdf.name

            try:
                run_pipeline(
                    input_pdf=pdf_path,
                    output_dir=tmpdir,
                    config_path=None,
                    verbose=False,
                )

                # Verify extraction was called
                mock_extraction_instance.run.assert_called_once_with(pdf_path)

                # Verify config was saved
                config_file = Path(tmpdir) / "config_used.json"
                assert config_file.exists()

                # Verify extraction report was saved
                report_file = Path(tmpdir) / "extraction_report.json"
                assert report_file.exists()

            finally:
                Path(pdf_path).unlink()

    @patch("src.main.ExtractionPhase")
    @patch("src.main.validate_pdf_path")
    @patch("src.main.validate_output_dir")
    def test_run_pipeline_with_config(
        self, mock_validate_output, mock_validate_pdf, mock_extraction
    ):
        """Test pipeline execution with custom config."""
        # Setup mocks
        mock_extraction_instance = MagicMock()
        mock_extraction.return_value = mock_extraction_instance

        mock_metadata = MagicMock()
        mock_metadata.total_blocks = 50
        mock_metadata.total_characters = 5000
        mock_metadata.total_pages = 5

        mock_extraction_instance.run.return_value = ([], mock_metadata)

        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                pdf_path = tmp_pdf.name

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as tmp_config:
                config_dict = {
                    "extraction": {"library": "pdfplumber"},
                    "chunking": {"max_chunk_size": 1000},
                }
                json.dump(config_dict, tmp_config)
                config_path = tmp_config.name

            try:
                run_pipeline(
                    input_pdf=pdf_path,
                    output_dir=tmpdir,
                    config_path=config_path,
                    verbose=False,
                )

                # Verify extraction was called
                mock_extraction_instance.run.assert_called_once_with(pdf_path)

            finally:
                Path(pdf_path).unlink()
                Path(config_path).unlink()

    @patch("src.main.validate_pdf_path")
    def test_run_pipeline_invalid_pdf(self, mock_validate_pdf):
        """Test pipeline with invalid PDF path."""
        mock_validate_pdf.side_effect = FileNotFoundError("PDF not found")

        with pytest.raises(FileNotFoundError):
            run_pipeline(
                input_pdf="/nonexistent/file.pdf",
                output_dir="output/",
                config_path=None,
                verbose=False,
            )

    @patch("src.main.validate_output_dir")
    @patch("src.main.validate_pdf_path")
    def test_run_pipeline_invalid_output_dir(
        self, mock_validate_pdf, mock_validate_output
    ):
        """Test pipeline with invalid output directory."""
        mock_validate_output.side_effect = ValueError("Invalid output directory")

        with pytest.raises(ValueError):
            run_pipeline(
                input_pdf="test.pdf",
                output_dir="/invalid/output/",
                config_path=None,
                verbose=False,
            )
