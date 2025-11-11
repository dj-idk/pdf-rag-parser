# Extraction Phase Documentation

## Overview

The Extraction Phase is the first step in the PDF RAG Parser pipeline. It handles the extraction of text and metadata from PDF documents using configurable extraction libraries.

## Features

- **Dual Library Support**: Choose between PyMuPDF (fitz) and pdfplumber
- **Metadata Extraction**: Automatically extracts document metadata and bookmarks
- **Font Information**: Captures font properties (name, size, weight, style)
- **Spatial Information**: Preserves bounding box coordinates for layout analysis
- **Error Handling**: Robust error handling and logging

## Architecture

### Core Components

#### TextBlock

Represents a single text block extracted from a PDF page.

```python
@dataclass
class TextBlock:
    content: str              # Text content
    page_num: int             # 1-indexed page number
    x0, y0, x1, y1: float    # Bounding box coordinates
    font_name: Optional[str]  # Font name
    font_size: Optional[float] # Font size in points
    is_bold: bool             # Bold flag
    is_italic: bool           # Italic flag
    char_count: int           # Character count
```

#### ExtractionMetadata

Contains metadata about the extraction process.

```python
@dataclass
class ExtractionMetadata:
    source_pdf: str           # Original PDF filename
    total_pages: int          # Total pages in PDF
    total_blocks: int         # Total text blocks extracted
    total_characters: int     # Total characters extracted
    extraction_library: str   # Library used (pymupdf/pdfplumber)
    extraction_timestamp: str # ISO format timestamp
    has_bookmarks: bool       # Whether PDF has bookmarks
    bookmarks: Optional[List] # Bookmark/TOC data
```

### Extractors

#### PyMuPDFExtractor

Uses PyMuPDF (fitz) for extraction. Advantages:

- Fast extraction
- Good font information
- Reliable bookmark extraction
- Better handling of complex layouts

#### PDFPlumberExtractor

Uses pdfplumber for extraction. Advantages:

- Excellent table detection
- Better text ordering
- More detailed character information
- Good for structured documents

### ExtractionPhase

Orchestrator class that manages the extraction process.

```python
phase = ExtractionPhase(config)
text_blocks, metadata = phase.run(pdf_path)
phase.save_extraction_report(metadata, report_path)
```

## Configuration

Configure extraction behavior via the config file:

```json
{
  "extraction": {
    "library": "pymupdf",
    "extract_metadata": true
  }
}
```

### Configuration Options

| Option             | Type    | Default   | Description               |
| ------------------ | ------- | --------- | ------------------------- |
| `library`          | string  | "pymupdf" | Extraction library to use |
| `extract_metadata` | boolean | true      | Extract document metadata |

## Usage Examples

### Basic Usage

```python
from src.phases.extraction import ExtractionPhase

# Create extractor with default config
phase = ExtractionPhase()

# Extract from PDF
text_blocks, metadata = phase.run("document.pdf")

# Access results
print(f"Extracted {metadata.total_blocks} blocks")
print(f"Total characters: {metadata.total_characters}")
```

### Custom Configuration

```python
from src.phases.extraction import ExtractionPhase

config = {
    "library": "pdfplumber",
    "extract_metadata": True
}

phase = ExtractionPhase(config)
text_blocks, metadata = phase.run("document.pdf")
```

### Saving Reports

```python
phase = ExtractionPhase()
text_blocks, metadata = phase.run("document.pdf")

# Save extraction report
phase.save_extraction_report(metadata, "output/extraction_report.json")
```

### Using Factory Function

```python
from src.phases.extraction import create_extractor

phase = create_extractor("document.pdf")
text_blocks, metadata = phase.run("document.pdf")
```

## Output Format

### Text Blocks

Each `TextBlock` contains:

- **content**: The actual text
- **page_num**: Page number (1-indexed)
- **Bounding box**: x0, y0, x1, y1 coordinates
- **Font info**: name, size, bold, italic flags
- **char_count**: Number of characters

### Extraction Report

JSON report saved with metadata:

```json
{
  "source_pdf": "document.pdf",
  "total_pages": 100,
  "total_blocks": 5000,
  "total_characters": 500000,
  "extraction_library": "pymupdf",
  "extraction_timestamp": "2024-01-15T10:30:00.123456",
  "has_bookmarks": true,
  "bookmarks": [
    {
      "level": 1,
      "title": "Chapter 1",
      "page": 1
    }
  ]
}
```

## Error Handling

The extraction phase handles various error scenarios:

```python
from src.phases.extraction import ExtractionPhase

try:
    phase = ExtractionPhase()
    text_blocks, metadata = phase.run("document.pdf")
except FileNotFoundError:
    print("PDF file not found")
except ValueError as e:
    print(f"Invalid input: {e}")
except Exception as e:
    print(f"Extraction failed: {e}")
```

## Performance Considerations

### Library Selection

**PyMuPDF (Default)**

- Faster extraction
- Better for large documents
- More reliable font detection
- Recommended for most use cases

**pdfplumber**

- Better for structured documents
- Excellent table detection
- Slower for large documents
- Better for complex layouts

### Optimization Tips

1. Use PyMuPDF for large documents (>100 pages)
2. Use pdfplumber for structured documents with tables
3. Disable metadata extraction if not needed:
   ```python
   config = {"extract_metadata": False}
   ```
4. Process in batches for multiple PDFs

## Testing

Run extraction tests:

```bash
pytest tests/test_extraction.py -v
pytest tests/test_extraction.py::TestPyMuPDFExtractor -v
pytest tests/test_extraction.py::TestPDFPlumberExtractor -v
```

## Troubleshooting

### ImportError: pymupdf not installed

```bash
pip install pymupdf
```

### ImportError: pdfplumber not installed

```bash
pip install pdfplumber
```

### Extraction produces empty results

- Check if PDF is corrupted
- Try switching extraction library
- Verify PDF is not encrypted

### Font information missing

- Some PDFs don't embed font information
- pdfplumber may have better results
- This is expected for scanned PDFs

## Next Steps

After extraction, text blocks proceed to:

1. **Structure Analysis** - Identify document hierarchy
2. **Cleaning & Filtering** - Remove noise
3. **Smart Chunking** - Create semantic chunks
4. **File Organization** - Save organized output

## API Reference

### ExtractionPhase

```python
class ExtractionPhase:
    def __init__(self, config: Optional[Dict] = None)
    def run(self, pdf_path: str) -> Tuple[List[TextBlock], ExtractionMetadata]
    def save_extraction_report(self, metadata: ExtractionMetadata, output_path: str) -> None
```

### PDFExtractor (Base Class)

```python
class PDFExtractor:
    def __init__(self, pdf_path: str, config: Optional[Dict] = None)
    def extract(self) -> Tuple[List[TextBlock], ExtractionMetadata]
    def _sanitize_text(self, text: str) -> str
```

### PyMuPDFExtractor

```python
class PyMuPDFExtractor(PDFExtractor):
    def extract(self) -> Tuple[List[TextBlock], ExtractionMetadata]
    def _extract_page_blocks(self, page: Any, page_num: int) -> List[TextBlock]
    def _extract_bookmarks(self) -> Optional[List[Dict[str, Any]]]
```

### PDFPlumberExtractor

```python
class PDFPlumberExtractor(PDFExtractor):
    def extract(self) -> Tuple[List[TextBlock], ExtractionMetadata]
    def _extract_page_blocks(self, page: Any, page_num: int) -> List[TextBlock]
    @staticmethod
    def _get_bbox(chars: List[Dict]) -> Tuple[float, float, float, float]
```

## Summary

The Extraction Phase provides a robust, configurable foundation for PDF text extraction. By supporting multiple extraction libraries and capturing comprehensive metadata, it enables the subsequent phases to perform accurate structure analysis, cleaning, and chunking operations. The modular design allows easy switching between extraction methods based on document characteristics and performance requirements.
