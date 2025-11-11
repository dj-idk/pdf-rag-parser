# PDF to RAG Parser

A robust, production-ready Python pipeline for converting PDF documents into semantically chunked, organized text files optimized for Retrieval-Augmented Generation (RAG) systems.

## Overview

This parser implements a **5-phase pipeline** that transforms raw PDFs into clean, structured, and RAG-ready text chunks:

1. **Text Extraction** - Extract text and metadata from PDFs
2. **Structure Analysis** - Identify document hierarchy (Parts, Chapters, Sections)
3. **Cleaning & Filtering** - Remove noise and unwanted sections
4. **Smart Chunking** - Split text into semantic chunks (≤800 characters)
5. **File Organization** - Save chunks in organized folder structure

## Why This Matters for RAG

RAG systems are only as good as their input data. A flawed pipeline creates a **"garbage in, garbage out"** problem:

- **Poor extraction** → Missing or corrupted text
- **No structure analysis** → Loss of document hierarchy
- **Inadequate cleaning** → Headers, footers, and noise pollute embeddings
- **Dumb chunking** → Sentences split mid-word, losing semantic meaning
- **Disorganized output** → Difficult to trace chunks back to source

This parser solves all of these problems.

---

## The 5-Phase Pipeline Explained

### Phase 1: Text Extraction

**Goal:** Extract all text and metadata from the PDF.

**What We Extract:**

- Raw text content
- Font size, font name, and font weight
- (x, y) coordinates on the page
- Page numbers

**Libraries Used:**

- `pymupdf` (Fitz) - Fast, reliable, excellent metadata support
- `pdfplumber` - Alternative for complex layouts

**Key Challenge:** PDFs are visual containers, not text documents.

- **Digital PDFs** (best case): Text is selectable; we can extract metadata
- **Scanned PDFs** (worst case): Would require OCR (not implemented in v1)

---

### Phase 2: Structure Analysis

**Goal:** Identify the document's hierarchy.

**What We Identify:**

- `PART_HEADING` - e.g., "Part I: The Beginning"
- `CHAPTER_HEADING` - e.g., "Chapter 3: The Journey"
- `SECTION_HEADING` - e.g., "3.1 Introduction"
- `BODY_TEXT` - Regular paragraph text
- `HEADER` / `FOOTER` - Page headers and footers

**Detection Methods (in order of reliability):**

1. **Bookmarks** - If the PDF has a built-in Table of Contents (bookmarks), we extract it directly. This is the most reliable method.

2. **Heuristics** - We analyze text properties:

   - Font size (larger = likely a heading)
   - Font weight (bold = likely a heading)
   - Text position (centered = likely a heading)
   - Isolation (alone on a line = likely a heading)

3. **Regex Patterns** - We search for common patterns:
   - `r"Chapter \d+"` - Chapter headings
   - `r"Part [IVX]+"` - Roman numeral parts
   - `r"\d+\.\d+ "` - Numbered sections

**Output:** Each text block is tagged with its type.

---

### Phase 3: Cleaning & Filtering

**Goal:** Remove noise and unwanted sections.

**What We Remove:**

- **Page numbers** - Usually at top/bottom of every page
- **Headers/Footers** - Repetitive text in fixed positions
- **Unwanted sections** - Index, Bibliography, Appendix (configurable)
- **Excessive whitespace** - Multiple blank lines

**How It Works:**

1. **Positional Filtering** - Define "crop boxes" to ignore areas (e.g., bottom 5% of page)
2. **Section Filtering** - Once we've identified structure, skip sections matching a blocklist
3. **Regex Filtering** - Remove patterns like page numbers (`[Page 123]`)

**Configuration:**

```json
{
  "exclude_sections": ["Index", "Bibliography", "Appendix"],
  "exclude_patterns": ["[Pp]age \\d+", "^\\s*$"],
  "crop_top_percent": 0,
  "crop_bottom_percent": 5
}
```

---

### Phase 4: Smart Chunking

**Goal:** Split cleaned text into semantically meaningful chunks (≤800 characters).

**Why "Smart" Chunking?**

Simply slicing every 800 characters breaks sentences and destroys semantic meaning. Instead, we respect natural boundaries:

1. **Paragraph-Level Splitting** - First boundary is paragraphs (`\n\n`)
2. **Sentence-Level Splitting** - If a paragraph exceeds 800 chars, split by sentences
3. **Word-Level Splitting** - Last resort: split by words to enforce the hard limit

**Algorithm:**

```
1. Start with an empty chunk
2. Add paragraphs one at a time
3. Check: Does chunk + next paragraph exceed 800 characters?
   - If NO: Add the paragraph, continue
   - If YES: Save current chunk, start new chunk with this paragraph
4. For oversized paragraphs (>800 chars):
   - Try splitting by sentences first
   - If sentence still >800 chars, split by words
5. Preserve chunk metadata (source chapter, section, etc.)
```

**Output:** Each chunk includes:

- Text content (≤800 characters)
- Source chapter/section
- Chunk sequence number
- Character count

---

### Phase 5: File Organization & Output

**Goal:** Save chunks in an organized, traceable folder structure.

**Folder Structure:**

```
output/
├── Part_I/
│   ├── Chapter_1_The_Beginning/
│   │   ├── chunk_001.txt
│   │   ├── chunk_002.txt
│   │   └── metadata.json
│   └── Chapter_2_The_Journey/
│       ├── chunk_001.txt
│       └── metadata.json
├── Part_II/
│   └── Chapter_3_The_Conclusion/
│       ├── chunk_001.txt
│       └── metadata.json
└── index.json
```

**What We Track:**

1. **Chunk Files** - Each chunk is a `.txt` file with semantic content
2. **Metadata Files** - Each chapter folder contains `metadata.json`:
   ```json
   {
     "chapter": "Chapter 1: The Beginning",
     "part": "Part I",
     "total_chunks": 5,
     "total_characters": 3847,
     "source_pages": [1, 2, 3]
   }
   ```
3. **Index File** - Root `index.json` maps the entire document structure:
   ```json
   {
     "source_pdf": "book.pdf",
     "total_chunks": 42,
     "total_characters": 31250,
     "structure": [
       {
         "part": "Part I",
         "chapters": [
           {
             "name": "Chapter 1: The Beginning",
             "chunks": 5,
             "path": "Part_I/Chapter_1_The_Beginning"
           }
         ]
       }
     ]
   }
   ```

**Filename Sanitization:**

Chapter titles are converted to safe folder names:

- `"Chapter 1: The Beginning"` → `Chapter_1_The_Beginning`
- Spaces → underscores
- Special characters removed
- Paths are URL-safe and cross-platform compatible

---

## Configuration Guide

Create a `config.json` file to customize the pipeline:

```json
{
  "extraction": {
    "library": "pymupdf",
    "extract_metadata": true
  },
  "structure": {
    "use_bookmarks": true,
    "use_heuristics": true,
    "use_regex": true,
    "font_size_threshold": 14,
    "heading_isolation_threshold": 0.7
  },
  "cleaning": {
    "exclude_sections": ["Index", "Bibliography", "Appendix", "References"],
    "exclude_patterns": ["[Pp]age \\d+", "^\\s*$", "^\\s*-{3,}\\s*$"],
    "crop_top_percent": 0,
    "crop_bottom_percent": 5,
    "crop_left_percent": 0,
    "crop_right_percent": 0
  },
  "chunking": {
    "max_chunk_size": 800,
    "chunk_overlap": 0,
    "split_by_paragraph": true,
    "split_by_sentence": true,
    "split_by_word": true
  },
  "output": {
    "output_dir": "output/",
    "create_metadata": true,
    "create_index": true,
    "preserve_structure": true
  }
}
```

---

## Getting Started

### Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd pdf-rag-parser
   ```

2. Create a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Basic Usage

```bash
python src.main.py --input path/to/book.pdf --output output/
```

### With Custom Configuration

```bash
python src.main.py --input path/to/book.pdf --output output/ --config config.json
```

### Command-Line Options

- `--input` - Path to input PDF file (required)
- `--output` - Output directory (default: `output/`)
- `--config` - Path to configuration JSON file (optional)
- `--verbose` - Enable verbose logging (optional)

---

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=src --cov-report=html
```

---

## Project Structure

```
pdf-rag-parser/
├── src/
│   ├── main.py                 # Entry point
│   ├── config.py               # Configuration management
│   ├── phases/
│   │   ├── extraction.py       # Phase 1: Text extraction
│   │   ├── structure.py        # Phase 2: Structure analysis
│   │   ├── cleaning.py         # Phase 3: Cleaning & filtering
│   │   ├── chunking.py         # Phase 4: Smart chunking
│   │   └── output.py           # Phase 5: File organization
│   └── utils/
│       ├── pdf_reader.py       # PDF reading utilities
│       ├── text_processor.py   # Text processing utilities
│       └── validators.py       # Input validation
├── tests/
│   ├── test_extraction.py
│   ├── test_structure.py
│   ├── test_cleaning.py
│   ├── test_chunking.py
│   └── test_output.py
├── requirements.txt
├── config.json
├── README.md
└── .gitignore
```

---

## Performance Considerations

- **Large PDFs (>500 pages):** Processing time scales linearly. Expect ~1-2 seconds per 100 pages
- **Memory Usage:** Typically <500MB for documents under 1000 pages
- **Extraction Library:** `pymupdf` is faster; `pdfplumber` is more accurate for complex layouts

---

## Known Limitations

1. **Scanned PDFs** - OCR not implemented in v1; requires digital PDFs with selectable text
2. **Complex Layouts** - Multi-column documents may have extraction issues
3. **Non-English PDFs** - Regex patterns optimized for English; may need customization
4. **Encrypted PDFs** - Password-protected PDFs not supported

---

## License

This project is not licensed. Feel free to use it however you want.
