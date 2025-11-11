"""
Phase 1: Text Extraction
Extracts text and metadata from PDF documents using configurable libraries.
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import json

try:
    import fitz  # pymupdf

    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    import pdfplumber

    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    """Represents a single text block extracted from a PDF."""

    content: str
    page_num: int
    x0: float
    y0: float
    x1: float
    y1: float
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    font_weight: Optional[str] = None
    is_bold: bool = False
    is_italic: bool = False
    char_count: int = 0

    def __post_init__(self):
        """Calculate character count if not set."""
        if self.char_count == 0:
            self.char_count = len(self.content)


@dataclass
class ExtractionMetadata:
    """Metadata about the extraction process."""

    source_pdf: str
    total_pages: int
    total_blocks: int
    total_characters: int
    extraction_library: str
    extraction_timestamp: str
    has_bookmarks: bool
    bookmarks: Optional[List[Dict[str, Any]]] = None


class PDFExtractor:
    """Base class for PDF extraction."""

    def __init__(self, pdf_path: str, config: Optional[Dict] = None):
        """
        Initialize the PDF extractor.

        Args:
            pdf_path: Path to the PDF file
            config: Configuration dictionary with extraction settings
        """
        self.pdf_path = Path(pdf_path)
        self.config = config or {}
        self.extract_metadata = self.config.get("extract_metadata", True)

        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        if not self.pdf_path.suffix.lower() == ".pdf":
            raise ValueError(f"File must be a PDF: {pdf_path}")

    def extract(self) -> Tuple[List[TextBlock], ExtractionMetadata]:
        """
        Extract text and metadata from PDF.

        Returns:
            Tuple of (text_blocks, metadata)
        """
        raise NotImplementedError("Subclasses must implement extract()")

    def _sanitize_text(self, text: str) -> str:
        """Remove null bytes and other problematic characters."""
        return text.replace("\x00", "").strip()


class PyMuPDFExtractor(PDFExtractor):
    """PDF extractor using PyMuPDF (fitz)."""

    def __init__(self, pdf_path: str, config: Optional[Dict] = None):
        """Initialize PyMuPDF extractor."""
        if not HAS_PYMUPDF:
            raise ImportError(
                "pymupdf is not installed. Install with: pip install pymupdf"
            )

        super().__init__(pdf_path, config)
        self.doc = None

    def extract(self) -> Tuple[List[TextBlock], ExtractionMetadata]:
        """
        Extract text and metadata using PyMuPDF.

        Returns:
            Tuple of (text_blocks, metadata)
        """
        logger.info(f"Extracting PDF using PyMuPDF: {self.pdf_path}")

        try:
            self.doc = fitz.open(str(self.pdf_path))
            text_blocks = []
            total_characters = 0
            bookmarks = None

            # Extract bookmarks if available
            if self.extract_metadata:
                bookmarks = self._extract_bookmarks()

            # Extract text from each page
            for page_num in range(len(self.doc)):
                page = self.doc[page_num]
                blocks = self._extract_page_blocks(page, page_num)
                text_blocks.extend(blocks)
                total_characters += sum(block.char_count for block in blocks)

            # Create metadata
            metadata = ExtractionMetadata(
                source_pdf=self.pdf_path.name,
                total_pages=len(self.doc),
                total_blocks=len(text_blocks),
                total_characters=total_characters,
                extraction_library="pymupdf",
                extraction_timestamp=self._get_timestamp(),
                has_bookmarks=bookmarks is not None and len(bookmarks) > 0,
                bookmarks=bookmarks,
            )

            logger.info(
                f"Extraction complete: {len(text_blocks)} blocks, "
                f"{total_characters} characters from {len(self.doc)} pages"
            )

            return text_blocks, metadata

        finally:
            if self.doc:
                self.doc.close()

    def _extract_page_blocks(self, page: Any, page_num: int) -> List[TextBlock]:
        """Extract text blocks from a single page."""
        blocks = []

        # Get text with layout information
        text_dict = page.get_text("dict")

        for block in text_dict.get("blocks", []):
            # Skip images and other non-text blocks
            if block["type"] != 0:
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    content = self._sanitize_text(span.get("text", ""))

                    if not content:
                        continue

                    # Extract font information
                    font_name = span.get("font", "")
                    font_size = span.get("size", 0)
                    is_bold = "bold" in font_name.lower()
                    is_italic = "italic" in font_name.lower()

                    # Get bounding box
                    bbox = span.get("bbox", (0, 0, 0, 0))

                    text_block = TextBlock(
                        content=content,
                        page_num=page_num + 1,  # 1-indexed
                        x0=bbox[0],
                        y0=bbox[1],
                        x1=bbox[2],
                        y1=bbox[3],
                        font_name=font_name if font_name else None,
                        font_size=font_size if font_size > 0 else None,
                        is_bold=is_bold,
                        is_italic=is_italic,
                    )

                    blocks.append(text_block)

        return blocks

    def _extract_bookmarks(self) -> Optional[List[Dict[str, Any]]]:
        """Extract bookmarks (table of contents) from PDF."""
        try:
            toc = self.doc.get_toc()
            if not toc:
                return None

            bookmarks = []
            for item in toc:
                level, title, page = item[0], item[1], item[2]
                bookmarks.append({"level": level, "title": title, "page": page})

            logger.info(f"Extracted {len(bookmarks)} bookmarks from PDF")
            return bookmarks if bookmarks else None

        except Exception as e:
            logger.warning(f"Failed to extract bookmarks: {e}")
            return None

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.now().isoformat()


class PDFPlumberExtractor(PDFExtractor):
    """PDF extractor using pdfplumber."""

    def __init__(self, pdf_path: str, config: Optional[Dict] = None):
        """Initialize pdfplumber extractor."""
        if not HAS_PDFPLUMBER:
            raise ImportError(
                "pdfplumber is not installed. Install with: pip install pdfplumber"
            )

        super().__init__(pdf_path, config)

    def extract(self) -> Tuple[List[TextBlock], ExtractionMetadata]:
        """
        Extract text and metadata using pdfplumber.

        Returns:
            Tuple of (text_blocks, metadata)
        """
        logger.info(f"Extracting PDF using pdfplumber: {self.pdf_path}")

        try:
            with pdfplumber.open(str(self.pdf_path)) as pdf:
                text_blocks = []
                total_characters = 0
                bookmarks = None

                # Extract bookmarks if available
                if self.extract_metadata:
                    bookmarks = self._extract_bookmarks(pdf)

                # Extract text from each page
                for page_num, page in enumerate(pdf.pages):
                    blocks = self._extract_page_blocks(page, page_num)
                    text_blocks.extend(blocks)
                    total_characters += sum(block.char_count for block in blocks)

                # Create metadata
                metadata = ExtractionMetadata(
                    source_pdf=self.pdf_path.name,
                    total_pages=len(pdf.pages),
                    total_blocks=len(text_blocks),
                    total_characters=total_characters,
                    extraction_library="pdfplumber",
                    extraction_timestamp=self._get_timestamp(),
                    has_bookmarks=bookmarks is not None and len(bookmarks) > 0,
                    bookmarks=bookmarks,
                )

                logger.info(
                    f"Extraction complete: {len(text_blocks)} blocks, "
                    f"{total_characters} characters from {len(pdf.pages)} pages"
                )

                return text_blocks, metadata

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise

    def _extract_page_blocks(self, page: Any, page_num: int) -> List[TextBlock]:
        """Extract text blocks from a single page."""
        blocks = []

        # Get characters with layout information
        chars = page.chars

        if not chars:
            return blocks

        # Group characters into blocks
        current_block = []
        current_y = chars[0]["top"]

        for char in chars:
            # Start new block if y-position changes significantly
            if abs(char["top"] - current_y) > 5 and current_block:
                block_text = "".join([c["text"] for c in current_block])
                block_text = self._sanitize_text(block_text)

                if block_text:
                    bbox = self._get_bbox(current_block)
                    font_size = current_block[0].get("size", 0)

                    text_block = TextBlock(
                        content=block_text,
                        page_num=page_num + 1,  # 1-indexed
                        x0=bbox[0],
                        y0=bbox[1],
                        x1=bbox[2],
                        y1=bbox[3],
                        font_size=font_size if font_size > 0 else None,
                    )

                    blocks.append(text_block)

                current_block = []
                current_y = char["top"]

            current_block.append(char)

        # Don't forget the last block
        if current_block:
            block_text = "".join([c["text"] for c in current_block])
            block_text = self._sanitize_text(block_text)

            if block_text:
                bbox = self._get_bbox(current_block)
                font_size = current_block[0].get("size", 0)

                text_block = TextBlock(
                    content=block_text,
                    page_num=page_num + 1,
                    x0=bbox[0],
                    y0=bbox[1],
                    x1=bbox[2],
                    y1=bbox[3],
                    font_size=font_size if font_size > 0 else None,
                )

                blocks.append(text_block)

        return blocks

    @staticmethod
    def _get_bbox(chars: List[Dict]) -> Tuple[float, float, float, float]:
        """Calculate bounding box from character list."""
        if not chars:
            return (0, 0, 0, 0)

        x0 = min(c["x0"] for c in chars)
        y0 = min(c["top"] for c in chars)
        x1 = max(c["x1"] for c in chars)
        y1 = max(c["bottom"] for c in chars)

        return (x0, y0, x1, y1)

    def _extract_bookmarks(self, pdf: Any) -> Optional[List[Dict[str, Any]]]:
        """Extract bookmarks from PDF."""
        try:
            if not hasattr(pdf, "outline"):
                return None

            bookmarks = []

            def process_outline(outline, level=0):
                for item in outline:
                    if isinstance(item, list):
                        process_outline(item, level + 1)
                    else:
                        title = item.get("title", "")
                        page = item.get("page", 0)
                        bookmarks.append({"level": level, "title": title, "page": page})

            process_outline(pdf.outline)

            if bookmarks:
                logger.info(f"Extracted {len(bookmarks)} bookmarks from PDF")
                return bookmarks

            return None

        except Exception as e:
            logger.warning(f"Failed to extract bookmarks: {e}")
            return None

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.now().isoformat()


class ExtractionPhase:
    """Orchestrates the extraction phase of the pipeline."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the extraction phase.

        Args:
            config: Configuration dictionary with extraction settings
        """
        self.config = config or {}
        self.library = self.config.get("library", "pymupdf").lower()

        # Validate library choice
        if self.library == "pymupdf" and not HAS_PYMUPDF:
            raise ImportError(
                "pymupdf not installed. Install with: pip install pymupdf"
            )

        if self.library == "pdfplumber" and not HAS_PDFPLUMBER:
            raise ImportError(
                "pdfplumber not installed. Install with: pip install pdfplumber"
            )

        if self.library not in ["pymupdf", "pdfplumber"]:

            raise ValueError(f"Unknown extraction library: {self.library}")

    def run(self, pdf_path: str) -> Tuple[List[TextBlock], ExtractionMetadata]:
        """
        Run the extraction phase on a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Tuple of (text_blocks, metadata)
        """
        logger.info(f"Starting extraction phase with {self.library}")

        if self.library == "pymupdf":
            extractor = PyMuPDFExtractor(pdf_path, self.config)
        else:
            extractor = PDFPlumberExtractor(pdf_path, self.config)

        text_blocks, metadata = extractor.extract()

        logger.info(
            f"Extraction phase complete: {metadata.total_blocks} blocks extracted"
        )

        return text_blocks, metadata

    def save_extraction_report(
        self, metadata: ExtractionMetadata, output_path: str
    ) -> None:
        """
        Save extraction metadata to a JSON report.

        Args:
            metadata: Extraction metadata
            output_path: Path to save the report
        """
        report = {
            "source_pdf": metadata.source_pdf,
            "total_pages": metadata.total_pages,
            "total_blocks": metadata.total_blocks,
            "total_characters": metadata.total_characters,
            "extraction_library": metadata.extraction_library,
            "extraction_timestamp": metadata.extraction_timestamp,
            "has_bookmarks": metadata.has_bookmarks,
            "bookmarks": metadata.bookmarks,
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Extraction report saved to: {output_path}")


def create_extractor(pdf_path: str, config: Optional[Dict] = None) -> ExtractionPhase:
    """
    Factory function to create an extraction phase instance.

    Args:
        pdf_path: Path to the PDF file
        config: Configuration dictionary

    Returns:
        ExtractionPhase instance
    """
    return ExtractionPhase(config)
