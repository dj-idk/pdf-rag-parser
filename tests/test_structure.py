import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.phases.extraction import TextBlock, ExtractionMetadata
from src.phases.structure import (
    TextBlockType,
    StructuredTextBlock,
    BookmarkAnalyzer,
    HeuristicAnalyzer,
    RegexAnalyzer,
    StructurePhase,
    create_structure_analyzer,
)


class TestTextBlockType:
    """Test TextBlockType enum."""

    def test_text_block_types_exist(self):
        """Test that all required text block types exist."""
        assert TextBlockType.PART_HEADING
        assert TextBlockType.CHAPTER_HEADING
        assert TextBlockType.SECTION_HEADING
        assert TextBlockType.SUBSECTION_HEADING
        assert TextBlockType.BODY_TEXT
        assert TextBlockType.HEADER
        assert TextBlockType.FOOTER
        assert TextBlockType.UNKNOWN


class TestStructuredTextBlock:
    """Test StructuredTextBlock dataclass."""

    def test_create_structured_block(self):
        """Test creating a structured text block."""
        block = StructuredTextBlock(
            content="Chapter 1: Introduction",
            page_num=1,
            x0=0,
            y0=0,
            x1=100,
            y1=50,
            block_type=TextBlockType.CHAPTER_HEADING,
            font_size=18,
            is_bold=True,
            hierarchy_level=1,
        )

        assert block.content == "Chapter 1: Introduction"
        assert block.page_num == 1
        assert block.block_type == TextBlockType.CHAPTER_HEADING
        assert block.hierarchy_level == 1
        assert block.char_count == len("Chapter 1: Introduction")

    def test_structured_block_with_parent(self):
        """Test structured block with parent heading."""
        block = StructuredTextBlock(
            content="This is body text.",
            page_num=2,
            x0=0,
            y0=0,
            x1=100,
            y1=50,
            block_type=TextBlockType.BODY_TEXT,
            parent_heading="Chapter 1: Introduction",
            hierarchy_level=0,
        )

        assert block.parent_heading == "Chapter 1: Introduction"
        assert block.block_type == TextBlockType.BODY_TEXT


class TestBookmarkAnalyzer:
    """Test BookmarkAnalyzer."""

    def test_analyze_with_no_bookmarks(self):
        """Test analyzing with no bookmarks."""
        analyzer = BookmarkAnalyzer(None)
        page_to_type, page_to_level = analyzer.analyze()

        assert page_to_type == {}
        assert page_to_level == {}

    def test_analyze_with_bookmarks(self):
        """Test analyzing with bookmarks."""
        bookmarks = [
            {"level": 0, "title": "Part I", "page": 1},
            {"level": 1, "title": "Chapter 1", "page": 5},
            {"level": 2, "title": "Section 1.1", "page": 10},
        ]

        analyzer = BookmarkAnalyzer(bookmarks)
        page_to_type, page_to_level = analyzer.analyze()

        assert page_to_type[1] == TextBlockType.PART_HEADING
        assert page_to_type[5] == TextBlockType.CHAPTER_HEADING
        assert page_to_type[10] == TextBlockType.SECTION_HEADING

        assert page_to_level[1] == 0
        assert page_to_level[5] == 1
        assert page_to_level[10] == 2

    def test_analyze_with_deep_nesting(self):
        """Test analyzing with deeply nested bookmarks."""
        bookmarks = [
            {"level": 0, "title": "Part I", "page": 1},
            {"level": 1, "title": "Chapter 1", "page": 5},
            {"level": 2, "title": "Section 1.1", "page": 10},
            {"level": 3, "title": "Subsection 1.1.1", "page": 15},
        ]

        analyzer = BookmarkAnalyzer(bookmarks)
        page_to_type, page_to_level = analyzer.analyze()

        assert page_to_type[15] == TextBlockType.SUBSECTION_HEADING
        assert page_to_level[15] == 3


class TestHeuristicAnalyzer:
    """Test HeuristicAnalyzer."""

    def test_initialization_with_default_config(self):
        """Test initializing with default config."""
        analyzer = HeuristicAnalyzer()

        assert analyzer.font_size_threshold == 14
        assert analyzer.heading_isolation_threshold == 0.7

    def test_initialization_with_custom_config(self):
        """Test initializing with custom config."""
        config = {
            "font_size_threshold": 16,
            "heading_isolation_threshold": 0.8,
        }
        analyzer = HeuristicAnalyzer(config)

        assert analyzer.font_size_threshold == 16
        assert analyzer.heading_isolation_threshold == 0.8

    def test_analyze_simple_blocks(self):
        """Test analyzing simple text blocks."""
        blocks = [
            TextBlock(
                content="Chapter 1",
                page_num=1,
                x0=250,
                y0=100,
                x1=350,
                y1=150,
                font_size=18,
                is_bold=True,
                char_count=9,
            ),
            TextBlock(
                content="This is body text.",
                page_num=1,
                x0=50,
                y0=200,
                x1=550,
                y1=220,
                font_size=12,
                is_bold=False,
                char_count=18,
            ),
        ]

        analyzer = HeuristicAnalyzer()
        block_types, block_to_level = analyzer.analyze(blocks)

        assert len(block_types) == 2
        assert block_types[0] != TextBlockType.BODY_TEXT  # Should be a heading
        assert block_types[1] == TextBlockType.BODY_TEXT

    def test_is_header_or_footer(self):
        """Test header/footer detection."""
        analyzer = HeuristicAnalyzer()

        # Header block (top of page, short text)
        header_block = TextBlock(
            content="Page Header",
            page_num=1,
            x0=0,
            y0=10,
            x1=600,
            y1=30,
            font_size=10,
            char_count=11,
        )

        # Footer block (bottom of page, short text)
        footer_block = TextBlock(
            content="Page 1",
            page_num=1,
            x0=0,
            y0=750,
            x1=600,
            y1=770,
            font_size=10,
            char_count=6,
        )

        # Body block (middle of page)
        body_block = TextBlock(
            content="This is body text.",
            page_num=1,
            x0=0,
            y0=400,
            x1=600,
            y1=420,
            font_size=12,
            char_count=18,
        )

        assert analyzer._is_header_or_footer(header_block)
        assert analyzer._is_header_or_footer(footer_block)
        assert not analyzer._is_header_or_footer(body_block)

    def test_is_centered(self):
        """Test center detection."""
        analyzer = HeuristicAnalyzer()
        analyzer.page_widths[1] = 600

        # Centered block
        centered_block = TextBlock(
            content="Centered Title",
            page_num=1,
            x0=250,
            y0=100,
            x1=350,
            y1=120,
            char_count=14,
        )

        # Left-aligned block
        left_block = TextBlock(
            content="Left aligned",
            page_num=1,
            x0=50,
            y0=100,
            x1=150,
            y1=120,
            char_count=12,
        )

        assert analyzer._is_centered(centered_block)
        assert not analyzer._is_centered(left_block)


class TestRegexAnalyzer:
    """Test RegexAnalyzer."""

    def test_initialization(self):
        """Test regex analyzer initialization."""
        analyzer = RegexAnalyzer()
        assert analyzer.patterns is not None
        assert len(analyzer.patterns) > 0

    def test_analyze_chapter_pattern(self):
        """Test analyzing chapter pattern."""
        blocks = [
            TextBlock(
                content="Chapter 1: Introduction",
                page_num=1,
                x0=0,
                y0=100,
                x1=600,
                y1=120,
                char_count=23,
            ),
            TextBlock(
                content="This is body text.",
                page_num=1,
                x0=0,
                y0=150,
                x1=600,
                y1=170,
                char_count=18,
            ),
        ]

        analyzer = RegexAnalyzer()
        block_types, block_to_level = analyzer.analyze(blocks)

        assert block_types[0] == TextBlockType.CHAPTER_HEADING
        assert block_types[1] == TextBlockType.BODY_TEXT

    def test_analyze_part_pattern(self):
        """Test analyzing part pattern."""
        blocks = [
            TextBlock(
                content="Part I: The Beginning",
                page_num=1,
                x0=0,
                y0=100,
                x1=600,
                y1=120,
                char_count=21,
            ),
        ]

        analyzer = RegexAnalyzer()
        block_types, block_to_level = analyzer.analyze(blocks)

        assert block_types[0] == TextBlockType.PART_HEADING

    def test_analyze_section_pattern(self):
        """Test analyzing section pattern."""
        blocks = [
            TextBlock(
                content="1.1 Introduction",
                page_num=1,
                x0=0,
                y0=100,
                x1=600,
                y1=120,
                char_count=15,
            ),
        ]

        analyzer = RegexAnalyzer()
        block_types, block_to_level = analyzer.analyze(blocks)

        assert block_types[0] == TextBlockType.SECTION_HEADING

    def test_analyze_subsection_pattern(self):
        """Test analyzing subsection pattern."""
        blocks = [
            TextBlock(
                content="1.1.1 Background",
                page_num=1,
                x0=0,
                y0=100,
                x1=600,
                y1=120,
                char_count=15,
            ),
        ]

        analyzer = RegexAnalyzer()
        block_types, block_to_level = analyzer.analyze(blocks)

        assert block_types[0] == TextBlockType.SUBSECTION_HEADING


class TestStructurePhase:
    """Test StructurePhase."""

    def test_initialization_with_default_config(self):
        """Test initializing with default config."""
        phase = StructurePhase()

        assert phase.use_bookmarks is True
        assert phase.use_heuristics is True
        assert phase.use_regex is True

    def test_initialization_with_custom_config(self):
        """Test initializing with custom config."""
        config = {
            "use_bookmarks": False,
            "use_heuristics": True,
            "use_regex": False,
        }
        phase = StructurePhase(config)

        assert phase.use_bookmarks is False
        assert phase.use_heuristics is True
        assert phase.use_regex is False

    def test_run_with_bookmarks(self):
        """Test running structure analysis with bookmarks."""
        text_blocks = [
            TextBlock(
                content="Part I",
                page_num=1,
                x0=0,
                y0=100,
                x1=600,
                y1=120,
                font_size=18,
                is_bold=True,
                char_count=6,
            ),
            TextBlock(
                content="Chapter 1",
                page_num=5,
                x0=0,
                y0=100,
                x1=600,
                y1=120,
                font_size=16,
                is_bold=True,
                char_count=9,
            ),
            TextBlock(
                content="Body text here.",
                page_num=6,
                x0=0,
                y0=150,
                x1=600,
                y1=170,
                font_size=12,
                char_count=15,
            ),
        ]

        bookmarks = [
            {"level": 0, "title": "Part I", "page": 1},
            {"level": 1, "title": "Chapter 1", "page": 5},
        ]

        extraction_metadata = ExtractionMetadata(
            source_pdf="test.pdf",
            total_pages=10,
            total_blocks=3,
            total_characters=30,
            extraction_library="pymupdf",
            extraction_timestamp="2024-01-01T00:00:00",
            has_bookmarks=True,
            bookmarks=bookmarks,
        )

        phase = StructurePhase({"use_bookmarks": True, "use_heuristics": False})
        structured_blocks, metadata = phase.run(text_blocks, extraction_metadata)

        assert len(structured_blocks) == 3
        assert metadata.parts_found >= 1
        assert metadata.chapters_found >= 1
        assert "bookmarks" in metadata.structure_method

    def test_run_with_heuristics_only(self):
        """Test running structure analysis with heuristics only."""
        text_blocks = [
            TextBlock(
                content="Chapter 1: Introduction",
                page_num=1,
                x0=250,
                y0=100,
                x1=350,
                y1=150,
                font_size=18,
                is_bold=True,
                char_count=23,
            ),
            TextBlock(
                content="This is body text.",
                page_num=1,
                x0=50,
                y0=200,
                x1=550,
                y1=220,
                font_size=12,
                is_bold=False,
                char_count=18,
            ),
        ]

        extraction_metadata = ExtractionMetadata(
            source_pdf="test.pdf",
            total_pages=1,
            total_blocks=2,
            total_characters=41,
            extraction_library="pymupdf",
            extraction_timestamp="2024-01-01T00:00:00",
            has_bookmarks=False,
            bookmarks=None,
        )

        phase = StructurePhase(
            {"use_bookmarks": False, "use_heuristics": True, "use_regex": False}
        )
        structured_blocks, metadata = phase.run(text_blocks, extraction_metadata)

        assert len(structured_blocks) == 2
        assert "heuristics" in metadata.structure_method

    def test_run_with_regex_only(self):
        """Test running structure analysis with regex only."""
        text_blocks = [
            TextBlock(
                content="Chapter 1: Introduction",
                page_num=1,
                x0=0,
                y0=100,
                x1=600,
                y1=120,
                font_size=14,
                char_count=23,
            ),
            TextBlock(
                content="Body text.",
                page_num=1,
                x0=0,
                y0=150,
                x1=600,
                y1=170,
                font_size=12,
                char_count=10,
            ),
        ]

        extraction_metadata = ExtractionMetadata(
            source_pdf="test.pdf",
            total_pages=1,
            total_blocks=2,
            total_characters=33,
            extraction_library="pymupdf",
            extraction_timestamp="2024-01-01T00:00:00",
            has_bookmarks=False,
            bookmarks=None,
        )

        phase = StructurePhase(
            {"use_bookmarks": False, "use_heuristics": False, "use_regex": True}
        )
        structured_blocks, metadata = phase.run(text_blocks, extraction_metadata)

        assert len(structured_blocks) == 2
        assert "regex" in metadata.structure_method

    def test_run_with_combined_methods(self):
        """Test running structure analysis with all methods."""
        text_blocks = [
            TextBlock(
                content="Part I: The Beginning",
                page_num=1,
                x0=250,
                y0=100,
                x1=350,
                y1=150,
                font_size=20,
                is_bold=True,
                char_count=21,
            ),
            TextBlock(
                content="Chapter 1: Introduction",
                page_num=5,
                x0=250,
                y0=100,
                x1=350,
                y1=150,
                font_size=18,
                is_bold=True,
                char_count=23,
            ),
            TextBlock(
                content="1.1 Background",
                page_num=10,
                x0=0,
                y0=100,
                x1=600,
                y1=120,
                font_size=14,
                char_count=14,
            ),
            TextBlock(
                content="This is body text with important information.",
                page_num=11,
                x0=0,
                y0=150,
                x1=600,
                y1=170,
                font_size=12,
                char_count=45,
            ),
        ]

        bookmarks = [
            {"level": 0, "title": "Part I: The Beginning", "page": 1},
            {"level": 1, "title": "Chapter 1: Introduction", "page": 5},
        ]

        extraction_metadata = ExtractionMetadata(
            source_pdf="test.pdf",
            total_pages=15,
            total_blocks=4,
            total_characters=103,
            extraction_library="pymupdf",
            extraction_timestamp="2024-01-01T00:00:00",
            has_bookmarks=True,
            bookmarks=bookmarks,
        )

        phase = StructurePhase(
            {
                "use_bookmarks": True,
                "use_heuristics": True,
                "use_regex": True,
            }
        )
        structured_blocks, metadata = phase.run(text_blocks, extraction_metadata)

        assert len(structured_blocks) == 4
        assert metadata.parts_found >= 1
        assert metadata.chapters_found >= 1
        assert metadata.sections_found >= 1
        assert "bookmarks" in metadata.structure_method
        assert "heuristics" in metadata.structure_method
        assert "regex" in metadata.structure_method

    def test_hierarchy_building(self):
        """Test building document hierarchy."""
        text_blocks = [
            TextBlock(
                content="Part I",
                page_num=1,
                x0=0,
                y0=100,
                x1=600,
                y1=120,
                font_size=20,
                is_bold=True,
                char_count=6,
            ),
            TextBlock(
                content="Chapter 1",
                page_num=5,
                x0=0,
                y0=100,
                x1=600,
                y1=120,
                font_size=18,
                is_bold=True,
                char_count=9,
            ),
            TextBlock(
                content="Section 1.1",
                page_num=10,
                x0=0,
                y0=100,
                x1=600,
                y1=120,
                font_size=14,
                is_bold=True,
                char_count=11,
            ),
        ]

        extraction_metadata = ExtractionMetadata(
            source_pdf="test.pdf",
            total_pages=15,
            total_blocks=3,
            total_characters=26,
            extraction_library="pymupdf",
            extraction_timestamp="2024-01-01T00:00:00",
            has_bookmarks=False,
            bookmarks=None,
        )

        phase = StructurePhase({"use_regex": True})
        structured_blocks, metadata = phase.run(text_blocks, extraction_metadata)

        # Check hierarchy structure
        assert len(metadata.hierarchy) > 0
        hierarchy = metadata.hierarchy[0]
        assert hierarchy["type"] in ["part", "chapter", "section"]

    def test_save_structure_report(self):
        """Test saving structure report."""
        from src.phases.structure import StructureMetadata

        metadata = StructureMetadata(
            total_blocks=100,
            classified_blocks=15,
            parts_found=1,
            chapters_found=5,
            sections_found=9,
            structure_method="bookmarks+heuristics",
            analysis_timestamp="2024-01-01T00:00:00",
            hierarchy=[
                {
                    "type": "part",
                    "title": "Part I",
                    "page": 1,
                    "chapters": [
                        {
                            "type": "chapter",
                            "title": "Chapter 1",
                            "page": 5,
                            "sections": [],
                        }
                    ],
                }
            ],
        )

        phase = StructurePhase()

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "structure_report.json"
            phase.save_structure_report(metadata, str(report_path))

            assert report_path.exists()

            import json

            with open(report_path, "r") as f:
                report = json.load(f)

            assert report["total_blocks"] == 100
            assert report["classified_blocks"] == 15
            assert report["parts_found"] == 1
            assert report["chapters_found"] == 5
            assert report["sections_found"] == 9
            assert report["structure_method"] == "bookmarks+heuristics"


class TestCreateStructureAnalyzer:
    """Test factory function."""

    def test_create_structure_analyzer(self):
        """Test creating structure analyzer via factory function."""
        phase = create_structure_analyzer()
        assert isinstance(phase, StructurePhase)

    def test_create_structure_analyzer_with_config(self):
        """Test creating structure analyzer with config."""
        config = {"use_bookmarks": False}
        phase = create_structure_analyzer(config)
        assert isinstance(phase, StructurePhase)
        assert phase.use_bookmarks is False
