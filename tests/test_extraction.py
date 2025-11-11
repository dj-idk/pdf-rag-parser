"""
Tests for the extraction phase.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.phases.extraction import (
    TextBlock,
    ExtractionMetadata,
    PDFExtractor,
    PyMuPDFExtractor,
    PDFPlumberExtractor,
    ExtractionPhase,
    create_extractor,
    HAS_PYMUPDF,
    HAS_PDFPLUMBER,
)


class TestTextBlock:
    """Test the TextBlock dataclass."""

    def test_text_block_creation(self):
        """Test creating a TextBlock."""
        block = TextBlock(
            content="Sample text",
            page_num=1,
            x0=10.0,
            y0=20.0,
            x1=100.0,
            y1=30.0,
            font_name="Arial",
            font_size=12.0,
            is_bold=False,
        )

        assert block.content == "Sample text"
        assert block.page_num == 1
        assert block.char_count == 11
        assert block.font_name == "Arial"

    def test_text_block_char_count(self):
        """Test automatic character count calculation."""
        block = TextBlock(content="Hello World", page_num=1, x0=0, y0=0, x1=100, y1=20)

        assert block.char_count == 11

    def test_text_block_with_empty_content(self):
        """Test TextBlock with empty content."""
        block = TextBlock(content="", page_num=1, x0=0, y0=0, x1=100, y1=20)

        assert block.char_count == 0


class TestExtractionMetadata:
    """Test the ExtractionMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating ExtractionMetadata."""
        metadata = ExtractionMetadata(
            source_pdf="test.pdf",
            total_pages=10,
            total_blocks=50,
            total_characters=5000,
            extraction_library="pymupdf",
            extraction_timestamp="2024-01-01T00:00:00",
            has_bookmarks=True,
            bookmarks=[{"level": 1, "title": "Chapter 1", "page": 1}],
        )

        assert metadata.source_pdf == "test.pdf"
        assert metadata.total_pages == 10
        assert metadata.has_bookmarks is True
        assert len(metadata.bookmarks) == 1


class TestPDFExtractor:
    """Test the base PDFExtractor class."""

    def test_extractor_initialization_with_valid_pdf(self):
        """Test initializing extractor with valid PDF path."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            extractor = PDFExtractor(tmp_path)
            assert extractor.pdf_path.exists()
            assert extractor.pdf_path.suffix == ".pdf"
        finally:
            Path(tmp_path).unlink()

    def test_extractor_initialization_with_missing_file(self):
        """Test initializing extractor with non-existent file."""
        with pytest.raises(FileNotFoundError):
            PDFExtractor("/nonexistent/path/file.pdf")

    def test_extractor_initialization_with_non_pdf_file(self):
        """Test initializing extractor with non-PDF file."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with pytest.raises(ValueError, match="File must be a PDF"):
                PDFExtractor(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_sanitize_text(self):
        """Test text sanitization."""
        extractor = PDFExtractor.__new__(PDFExtractor)

        # Test null byte removal
        result = extractor._sanitize_text("Hello\x00World")
        assert result == "HelloWorld"

        # Test whitespace stripping
        result = extractor._sanitize_text("  Hello World  ")
        assert result == "Hello World"

    def test_extract_not_implemented(self):
        """Test that extract() raises NotImplementedError."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            extractor = PDFExtractor(tmp_path)
            with pytest.raises(NotImplementedError):
                extractor.extract()
        finally:
            Path(tmp_path).unlink()


@pytest.mark.skipif(not HAS_PYMUPDF, reason="pymupdf not installed")
class TestPyMuPDFExtractor:
    """Test the PyMuPDF extractor."""

    def test_extractor_initialization(self):
        """Test initializing PyMuPDF extractor."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            extractor = PyMuPDFExtractor(tmp_path)
            assert extractor.pdf_path.exists()
        finally:
            Path(tmp_path).unlink()

    def test_get_timestamp(self):
        """Test timestamp generation."""
        timestamp = PyMuPDFExtractor._get_timestamp()
        assert "T" in timestamp  # ISO format includes T
        assert len(timestamp) > 10


@pytest.mark.skipif(not HAS_PDFPLUMBER, reason="pdfplumber not installed")
class TestPDFPlumberExtractor:
    """Test the pdfplumber extractor."""

    def test_extractor_initialization(self):
        """Test initializing pdfplumber extractor."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            extractor = PDFPlumberExtractor(tmp_path)
            assert extractor.pdf_path.exists()
        finally:
            Path(tmp_path).unlink()

    def test_get_bbox(self):
        """Test bounding box calculation."""
        chars = [
            {"x0": 10, "x1": 20, "top": 5, "bottom": 15},
            {"x0": 15, "x1": 25, "top": 5, "bottom": 15},
            {"x0": 20, "x1": 30, "top": 5, "bottom": 15},
        ]

        bbox = PDFPlumberExtractor._get_bbox(chars)
        assert bbox == (10, 5, 30, 15)

    def test_get_bbox_empty(self):
        """Test bounding box with empty character list."""
        bbox = PDFPlumberExtractor._get_bbox([])
        assert bbox == (0, 0, 0, 0)


class TestExtractionPhase:
    """Test the ExtractionPhase orchestrator."""

    def test_initialization_with_default_config(self):
        """Test initializing ExtractionPhase with default config."""
        if HAS_PYMUPDF:
            phase = ExtractionPhase()
            assert phase.library == "pymupdf"

    def test_initialization_with_custom_library(self):
        """Test initializing with custom library."""
        if HAS_PDFPLUMBER:
            config = {"library": "pdfplumber"}
            phase = ExtractionPhase(config)
            assert phase.library == "pdfplumber"

    def test_initialization_with_invalid_library(self):
        """Test initializing with invalid library."""
        config = {"library": "invalid_library"}
        with pytest.raises(ValueError, match="Unknown extraction library"):
            ExtractionPhase(config)

    def test_initialization_with_missing_library(self):
        """Test initializing when library is not installed."""
        config = {"library": "pymupdf"}
        if not HAS_PYMUPDF:
            with pytest.raises(ImportError):
                ExtractionPhase(config)

    def test_save_extraction_report(self):
        """Test saving extraction report."""
        metadata = ExtractionMetadata(
            source_pdf="test.pdf",
            total_pages=10,
            total_blocks=50,
            total_characters=5000,
            extraction_library="pymupdf",
            extraction_timestamp="2024-01-01T00:00:00",
            has_bookmarks=False,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"

            if HAS_PYMUPDF:
                phase = ExtractionPhase()
                phase.save_extraction_report(metadata, str(report_path))

                assert report_path.exists()

                with open(report_path, "r") as f:
                    report = json.load(f)

                assert report["source_pdf"] == "test.pdf"
                assert report["total_pages"] == 10
                assert report["total_blocks"] == 50


class TestFactoryFunction:
    """Test the factory function."""

    def test_create_extractor(self):
        """Test creating extractor via factory function."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            if HAS_PYMUPDF:
                phase = create_extractor(tmp_path)
                assert isinstance(phase, ExtractionPhase)
        finally:
            Path(tmp_path).unlink()


class TestExtractionIntegration:
    """Integration tests for extraction phase."""

    @pytest.mark.skipif(not HAS_PYMUPDF, reason="pymupdf not installed")
    def test_extraction_with_mock_pdf(self):
        """Test extraction with mocked PDF data."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("fitz.open") as mock_open:
                # Create mock document
                mock_doc = MagicMock()
                mock_doc.__len__ = MagicMock(return_value=1)
                mock_doc.__getitem__ = MagicMock()

                # Create mock page
                mock_page = MagicMock()
                mock_page.get_text.return_value = {
                    "blocks": [
                        {
                            "type": 0,
                            "lines": [
                                {
                                    "spans": [
                                        {
                                            "text": "Sample text",
                                            "font": "Arial",
                                            "size": 12,
                                            "bbox": (10, 20, 100, 30),
                                        }
                                    ]
                                }
                            ],
                        }
                    ]
                }

                mock_doc.__getitem__.return_value = mock_page
                mock_doc.get_toc.return_value = []
                mock_open.return_value = mock_doc

                extractor = PyMuPDFExtractor(tmp_path)
                blocks, metadata = extractor.extract()

                assert len(blocks) > 0
                assert metadata.total_pages == 1
                assert metadata.extraction_library == "pymupdf"

        finally:
            Path(tmp_path).unlink()
