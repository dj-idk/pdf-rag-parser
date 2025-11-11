"""
Tests for input validators.
"""

import pytest
import tempfile
from pathlib import Path

from src.utils.validators import (
    validate_pdf_path,
    validate_output_dir,
    validate_config_path,
)


class TestValidatePdfPath:
    """Test PDF path validation."""

    def test_valid_pdf_path(self):
        """Test validation with valid PDF path."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            validate_pdf_path(tmp_path)  # Should not raise
        finally:
            Path(tmp_path).unlink()

    def test_nonexistent_pdf_path(self):
        """Test validation with non-existent PDF path."""
        with pytest.raises(FileNotFoundError):
            validate_pdf_path("/nonexistent/file.pdf")

    def test_non_pdf_file(self):
        """Test validation with non-PDF file."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with pytest.raises(ValueError, match="not a PDF"):
                validate_pdf_path(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_directory_instead_of_file(self):
        """Test validation with directory instead of file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="not a file"):
                validate_pdf_path(tmpdir)


class TestValidateOutputDir:
    """Test output directory validation."""

    def test_valid_output_dir(self):
        """Test validation with valid output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validate_output_dir(tmpdir)  # Should not raise

    def test_nonexistent_parent_directory(self):
        """Test validation with non-existent parent directory."""
        with pytest.raises(ValueError, match="Parent directory does not exist"):
            validate_output_dir("/nonexistent/parent/output/")

    def test_output_path_is_file(self):
        """Test validation when output path is a file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with pytest.raises(ValueError, match="not a directory"):
                validate_output_dir(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_nonexistent_output_dir_valid_parent(self):
        """Test validation with non-existent output dir but valid parent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output"
            validate_output_dir(str(output_path))  # Should not raise


class TestValidateConfigPath:
    """Test configuration file validation."""

    def test_valid_config_path(self):
        """Test validation with valid config path."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            validate_config_path(tmp_path)  # Should not raise
        finally:
            Path(tmp_path).unlink()

    def test_nonexistent_config_path(self):
        """Test validation with non-existent config path."""
        with pytest.raises(FileNotFoundError):
            validate_config_path("/nonexistent/config.json")

    def test_non_json_config_file(self):
        """Test validation with non-JSON config file."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with pytest.raises(ValueError, match="must be JSON"):
                validate_config_path(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_directory_instead_of_config_file(self):
        """Test validation with directory instead of config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="not a file"):
                validate_config_path(tmpdir)
