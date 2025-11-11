from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import logging
import re
from pathlib import Path

from src.phases.extraction import TextBlock, ExtractionMetadata

logger = logging.getLogger(__name__)


class TextBlockType(Enum):
    """Classification of text block types."""

    PART_HEADING = "PART_HEADING"
    CHAPTER_HEADING = "CHAPTER_HEADING"
    SECTION_HEADING = "SECTION_HEADING"
    SUBSECTION_HEADING = "SUBSECTION_HEADING"
    BODY_TEXT = "BODY_TEXT"
    HEADER = "HEADER"
    FOOTER = "FOOTER"
    UNKNOWN = "UNKNOWN"


@dataclass
class StructuredTextBlock:
    """Text block with structural classification."""

    content: str
    page_num: int
    x0: float
    y0: float
    x1: float
    y1: float
    block_type: TextBlockType
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    font_weight: Optional[str] = None
    is_bold: bool = False
    is_italic: bool = False
    char_count: int = 0
    hierarchy_level: int = 0  # 0=Part, 1=Chapter, 2=Section, 3=Subsection
    parent_heading: Optional[str] = None

    def __post_init__(self):
        """Calculate character count if not set."""
        if self.char_count == 0:
            self.char_count = len(self.content)


@dataclass
class StructureMetadata:
    """Metadata about the structure analysis."""

    total_blocks: int
    classified_blocks: int
    parts_found: int
    chapters_found: int
    sections_found: int
    structure_method: str  # "bookmarks", "heuristics", "regex", "combined"
    analysis_timestamp: str
    hierarchy: List[Dict[str, Any]] = field(default_factory=list)


class BookmarkAnalyzer:
    """Analyzes document structure using PDF bookmarks."""

    def __init__(self, bookmarks: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize bookmark analyzer.

        Args:
            bookmarks: List of bookmarks from extraction phase
        """
        self.bookmarks = bookmarks or []

    def analyze(self) -> Tuple[Dict[int, TextBlockType], Dict[int, int]]:
        """
        Analyze bookmarks to determine heading levels.

        Returns:
            Tuple of (page_to_type_map, page_to_level_map)
        """
        page_to_type = {}
        page_to_level = {}

        if not self.bookmarks:
            return page_to_type, page_to_level

        for bookmark in self.bookmarks:
            level = bookmark.get("level", 0)
            page = bookmark.get("page", 0)

            # Map bookmark level to heading type
            if level == 0:
                block_type = TextBlockType.PART_HEADING
            elif level == 1:
                block_type = TextBlockType.CHAPTER_HEADING
            elif level == 2:
                block_type = TextBlockType.SECTION_HEADING
            else:
                block_type = TextBlockType.SUBSECTION_HEADING

            page_to_type[page] = block_type
            page_to_level[page] = level

        logger.info(f"Analyzed {len(self.bookmarks)} bookmarks")
        return page_to_type, page_to_level


class HeuristicAnalyzer:
    """Analyzes document structure using font and layout heuristics."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize heuristic analyzer.

        Args:
            config: Configuration dictionary with heuristic settings
        """
        self.config = config or {}
        self.font_size_threshold = self.config.get("font_size_threshold", 14)
        self.heading_isolation_threshold = self.config.get(
            "heading_isolation_threshold", 0.7
        )
        self.font_sizes: List[float] = []
        self.page_widths: Dict[int, float] = {}

    def analyze(
        self, text_blocks: List[TextBlock]
    ) -> Tuple[List[TextBlockType], Dict[int, int]]:
        """
        Analyze text blocks using heuristics.

        Args:
            text_blocks: List of extracted text blocks

        Returns:
            Tuple of (block_types, block_to_level_map)
        """
        # First pass: collect statistics
        self._collect_statistics(text_blocks)

        # Second pass: classify blocks
        block_types = []
        block_to_level = {}

        for idx, block in enumerate(text_blocks):
            block_type, level = self._classify_block(block, text_blocks, idx)
            block_types.append(block_type)
            block_to_level[idx] = level

        logger.info(
            f"Heuristic analysis complete: "
            f"{sum(1 for t in block_types if t != TextBlockType.BODY_TEXT)} "
            f"headings identified"
        )

        return block_types, block_to_level

    def _collect_statistics(self, text_blocks: List[TextBlock]) -> None:
        """Collect font size and page width statistics."""
        for block in text_blocks:
            if block.font_size and block.font_size > 0:
                self.font_sizes.append(block.font_size)

            page_width = block.x1 - block.x0
            if block.page_num not in self.page_widths:
                self.page_widths[block.page_num] = page_width
            else:
                self.page_widths[block.page_num] = max(
                    self.page_widths[block.page_num], page_width
                )

    def _classify_block(
        self, block: TextBlock, all_blocks: List[TextBlock], block_idx: int
    ) -> Tuple[TextBlockType, int]:
        """
        Classify a single text block.

        Returns:
            Tuple of (block_type, hierarchy_level)
        """
        # Check for header/footer (top/bottom of page)
        if self._is_header_or_footer(block):
            return TextBlockType.HEADER if block.y0 < 100 else TextBlockType.FOOTER, 0

        # Check for heading characteristics
        is_large_font = block.font_size and block.font_size >= self.font_size_threshold
        is_bold = block.is_bold
        is_isolated = self._is_isolated(block, all_blocks, block_idx)
        is_centered = self._is_centered(block)

        # Score heading likelihood
        heading_score = sum([is_large_font, is_bold, is_isolated, is_centered]) / 4.0

        if heading_score >= self.heading_isolation_threshold:
            # Determine heading level based on font size
            level = self._determine_heading_level(block)
            return self._get_heading_type(level), level

        return TextBlockType.BODY_TEXT, 0

    def _is_header_or_footer(self, block: TextBlock) -> bool:
        """Check if block is likely a header or footer."""
        # Headers typically in top 10% of page
        # Footers typically in bottom 10% of page
        page_height = 800  # Approximate page height in points

        is_top = block.y0 < page_height * 0.1
        is_bottom = block.y0 > page_height * 0.9

        # Short text is more likely to be header/footer
        is_short = len(block.content) < 100

        return (is_top or is_bottom) and is_short

    def _is_isolated(
        self, block: TextBlock, all_blocks: List[TextBlock], block_idx: int
    ) -> bool:
        """Check if block is isolated (alone on its line)."""
        # Check blocks before and after
        before_isolated = (
            block_idx == 0
            or all_blocks[block_idx - 1].page_num != block.page_num
            or abs(all_blocks[block_idx - 1].y1 - block.y0) > 20
        )

        after_isolated = (
            block_idx == len(all_blocks) - 1
            or all_blocks[block_idx + 1].page_num != block.page_num
            or abs(block.y1 - all_blocks[block_idx + 1].y0) > 20
        )

        return before_isolated and after_isolated

    def _is_centered(self, block: TextBlock) -> bool:
        """Check if block is centered on the page."""
        page_width = self.page_widths.get(block.page_num, 600)
        block_center = (block.x0 + block.x1) / 2
        page_center = page_width / 2

        # Within 10% of center
        return abs(block_center - page_center) < page_width * 0.1

    def _determine_heading_level(self, block: TextBlock) -> int:
        """Determine heading level based on font size."""
        if not block.font_size or not self.font_sizes:
            return 3  # Default to subsection

        # Calculate percentile
        sorted_sizes = sorted(self.font_sizes)
        percentile = sorted_sizes.index(block.font_size) / len(sorted_sizes)

        if percentile >= 0.9:
            return 0  # Part (largest)
        elif percentile >= 0.75:
            return 1  # Chapter
        elif percentile >= 0.6:
            return 2  # Section
        else:
            return 3  # Subsection

    @staticmethod
    def _get_heading_type(level: int) -> TextBlockType:
        """Convert level to heading type."""
        level_map = {
            0: TextBlockType.PART_HEADING,
            1: TextBlockType.CHAPTER_HEADING,
            2: TextBlockType.SECTION_HEADING,
            3: TextBlockType.SUBSECTION_HEADING,
        }
        return level_map.get(level, TextBlockType.BODY_TEXT)


class RegexAnalyzer:
    """Analyzes document structure using regex patterns."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize regex analyzer.

        Args:
            config: Configuration dictionary with regex patterns
        """
        self.config = config or {}
        self.patterns = self._build_patterns()

    def analyze(
        self, text_blocks: List[TextBlock]
    ) -> Tuple[List[TextBlockType], Dict[int, int]]:
        """
        Analyze text blocks using regex patterns.

        Args:
            text_blocks: List of extracted text blocks

        Returns:
            Tuple of (block_types, block_to_level_map)
        """
        block_types = []
        block_to_level = {}

        for idx, block in enumerate(text_blocks):
            block_type, level = self._classify_block(block)
            block_types.append(block_type)
            block_to_level[idx] = level

        logger.info(
            f"Regex analysis complete: "
            f"{sum(1 for t in block_types if t != TextBlockType.BODY_TEXT)} "
            f"headings identified"
        )

        return block_types, block_to_level

    def _build_patterns(self) -> Dict[TextBlockType, List[re.Pattern]]:
        """Build regex patterns for heading detection."""
        patterns = {
            TextBlockType.PART_HEADING: [
                re.compile(r"^Part\s+[IVX]+\s*:", re.IGNORECASE),
                re.compile(r"^Part\s+\d+\s*:", re.IGNORECASE),
            ],
            TextBlockType.CHAPTER_HEADING: [
                re.compile(r"^Chapter\s+\d+\s*:", re.IGNORECASE),
                re.compile(r"^Ch\.\s+\d+\s*:", re.IGNORECASE),
            ],
            TextBlockType.SECTION_HEADING: [
                re.compile(r"^\d+\.\d+\s+", re.IGNORECASE),
                re.compile(r"^Section\s+\d+\s*:", re.IGNORECASE),
            ],
            TextBlockType.SUBSECTION_HEADING: [
                re.compile(r"^\d+\.\d+\.\d+\s+", re.IGNORECASE),
            ],
        }
        return patterns

    def _classify_block(self, block: TextBlock) -> Tuple[TextBlockType, int]:
        """Classify block using regex patterns."""
        content = block.content.strip()

        # Check patterns in order of specificity
        for block_type, pattern_list in self.patterns.items():
            for pattern in pattern_list:
                if pattern.match(content):
                    level = self._get_level(block_type)
                    return block_type, level

        return TextBlockType.BODY_TEXT, 0

    @staticmethod
    def _get_level(block_type: TextBlockType) -> int:
        """Convert block type to hierarchy level."""
        level_map = {
            TextBlockType.PART_HEADING: 0,
            TextBlockType.CHAPTER_HEADING: 1,
            TextBlockType.SECTION_HEADING: 2,
            TextBlockType.SUBSECTION_HEADING: 3,
        }
        return level_map.get(block_type, 0)


class StructurePhase:
    """Orchestrates the structure analysis phase of the pipeline."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the structure analysis phase.

        Args:
            config: Configuration dictionary with structure settings
        """
        self.config = config or {}
        self.use_bookmarks = self.config.get("use_bookmarks", True)
        self.use_heuristics = self.config.get("use_heuristics", True)
        self.use_regex = self.config.get("use_regex", True)

    def run(
        self,
        text_blocks: List[TextBlock],
        extraction_metadata: ExtractionMetadata,
    ) -> Tuple[List[StructuredTextBlock], StructureMetadata]:
        """
        Run the structure analysis phase.

        Args:
            text_blocks: List of extracted text blocks
            extraction_metadata: Metadata from extraction phase

        Returns:
            Tuple of (structured_blocks, metadata)
        """
        logger.info("Starting structure analysis phase")

        # Initialize classification
        block_types = [TextBlockType.UNKNOWN] * len(text_blocks)
        block_levels = {i: 0 for i in range(len(text_blocks))}
        method_used = []

        # Method 1: Bookmarks (most reliable)
        if self.use_bookmarks and extraction_metadata.bookmarks:
            logger.info("Analyzing structure using bookmarks...")
            bookmark_analyzer = BookmarkAnalyzer(extraction_metadata.bookmarks)
            page_to_type, page_to_level = bookmark_analyzer.analyze()

            # Apply bookmark classifications
            for idx, block in enumerate(text_blocks):
                if block.page_num in page_to_type:
                    block_types[idx] = page_to_type[block.page_num]
                    block_levels[idx] = page_to_level[block.page_num]

            method_used.append("bookmarks")

        # Method 2: Heuristics (font size, bold, isolation, centering)
        if self.use_heuristics:
            logger.info("Analyzing structure using heuristics...")
            heuristic_analyzer = HeuristicAnalyzer(self.config)
            heuristic_types, heuristic_levels = heuristic_analyzer.analyze(text_blocks)

            # Apply heuristic classifications where bookmarks didn't classify
            for idx, block_type in enumerate(heuristic_types):
                if block_types[idx] == TextBlockType.UNKNOWN:
                    block_types[idx] = block_type
                    block_levels[idx] = heuristic_levels[idx]

            method_used.append("heuristics")

        # Method 3: Regex patterns (most specific)
        if self.use_regex:
            logger.info("Analyzing structure using regex patterns...")
            regex_analyzer = RegexAnalyzer(self.config)
            regex_types, regex_levels = regex_analyzer.analyze(text_blocks)

            # Apply regex classifications where others didn't classify
            for idx, block_type in enumerate(regex_types):
                if block_types[idx] == TextBlockType.UNKNOWN:
                    block_types[idx] = block_type
                    block_levels[idx] = regex_levels[idx]

            method_used.append("regex")

        # Default remaining unknown blocks to body text
        for idx in range(len(block_types)):
            if block_types[idx] == TextBlockType.UNKNOWN:
                block_types[idx] = TextBlockType.BODY_TEXT
                block_levels[idx] = 0

        # Create structured blocks
        structured_blocks = self._create_structured_blocks(
            text_blocks, block_types, block_levels
        )

        # Build hierarchy
        hierarchy = self._build_hierarchy(structured_blocks)

        # Create metadata
        metadata = StructureMetadata(
            total_blocks=len(text_blocks),
            classified_blocks=sum(
                1
                for t in block_types
                if t != TextBlockType.BODY_TEXT
                and t != TextBlockType.HEADER
                and t != TextBlockType.FOOTER
            ),
            parts_found=sum(1 for t in block_types if t == TextBlockType.PART_HEADING),
            chapters_found=sum(
                1 for t in block_types if t == TextBlockType.CHAPTER_HEADING
            ),
            sections_found=sum(
                1 for t in block_types if t == TextBlockType.SECTION_HEADING
            ),
            structure_method="+".join(method_used),
            analysis_timestamp=self._get_timestamp(),
            hierarchy=hierarchy,
        )

        logger.info(
            f"Structure analysis complete: {metadata.classified_blocks} headings found "
            f"({metadata.parts_found} parts, {metadata.chapters_found} chapters, "
            f"{metadata.sections_found} sections)"
        )

        return structured_blocks, metadata

    def _create_structured_blocks(
        self,
        text_blocks: List[TextBlock],
        block_types: List[TextBlockType],
        block_levels: Dict[int, int],
    ) -> List[StructuredTextBlock]:
        """Convert text blocks to structured blocks with hierarchy."""
        structured_blocks = []
        current_part = None
        current_chapter = None
        current_section = None

        for idx, (text_block, block_type) in enumerate(zip(text_blocks, block_types)):
            hierarchy_level = block_levels.get(idx, 0)

            # Track current hierarchy
            if block_type == TextBlockType.PART_HEADING:
                current_part = text_block.content
                current_chapter = None
                current_section = None
            elif block_type == TextBlockType.CHAPTER_HEADING:
                current_chapter = text_block.content
                current_section = None
            elif block_type == TextBlockType.SECTION_HEADING:
                current_section = text_block.content

            # Determine parent heading
            parent_heading = None
            if block_type == TextBlockType.BODY_TEXT:
                if current_section:
                    parent_heading = current_section
                elif current_chapter:
                    parent_heading = current_chapter
                elif current_part:
                    parent_heading = current_part

            structured_block = StructuredTextBlock(
                content=text_block.content,
                page_num=text_block.page_num,
                x0=text_block.x0,
                y0=text_block.y0,
                x1=text_block.x1,
                y1=text_block.y1,
                block_type=block_type,
                font_name=text_block.font_name,
                font_size=text_block.font_size,
                font_weight=text_block.font_weight,
                is_bold=text_block.is_bold,
                is_italic=text_block.is_italic,
                char_count=text_block.char_count,
                hierarchy_level=hierarchy_level,
                parent_heading=parent_heading,
            )

            structured_blocks.append(structured_block)

        return structured_blocks

    def _build_hierarchy(
        self, structured_blocks: List[StructuredTextBlock]
    ) -> List[Dict[str, Any]]:
        """Build a hierarchical representation of the document structure."""
        hierarchy = []
        current_part = None
        current_chapter = None
        current_section = None

        for block in structured_blocks:
            if block.block_type == TextBlockType.PART_HEADING:
                current_part = {
                    "type": "part",
                    "title": block.content,
                    "page": block.page_num,
                    "chapters": [],
                }
                hierarchy.append(current_part)
                current_chapter = None
                current_section = None

            elif block.block_type == TextBlockType.CHAPTER_HEADING:
                current_chapter = {
                    "type": "chapter",
                    "title": block.content,
                    "page": block.page_num,
                    "sections": [],
                }
                if current_part:
                    current_part["chapters"].append(current_chapter)
                else:
                    hierarchy.append(current_chapter)
                current_section = None

            elif block.block_type == TextBlockType.SECTION_HEADING:
                current_section = {
                    "type": "section",
                    "title": block.content,
                    "page": block.page_num,
                }
                if current_chapter:
                    current_chapter["sections"].append(current_section)
                elif current_part:
                    if not current_part["chapters"]:
                        current_part["chapters"].append(
                            {
                                "type": "chapter",
                                "title": "Unnamed Chapter",
                                "sections": [current_section],
                            }
                        )
                    else:
                        current_part["chapters"][-1]["sections"].append(current_section)

        return hierarchy

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.now().isoformat()

    def save_structure_report(
        self, metadata: StructureMetadata, output_path: str
    ) -> None:
        """
        Save structure analysis metadata to a JSON report.

        Args:
            metadata: Structure metadata
            output_path: Path to save the report
        """
        import json

        report = {
            "total_blocks": metadata.total_blocks,
            "classified_blocks": metadata.classified_blocks,
            "parts_found": metadata.parts_found,
            "chapters_found": metadata.chapters_found,
            "sections_found": metadata.sections_found,
            "structure_method": metadata.structure_method,
            "analysis_timestamp": metadata.analysis_timestamp,
            "hierarchy": metadata.hierarchy,
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Structure report saved to: {output_path}")


def create_structure_analyzer(
    config: Optional[Dict] = None,
) -> StructurePhase:
    """
    Factory function to create a structure analysis phase instance.

    Args:
        config: Configuration dictionary

    Returns:
        StructurePhase instance
    """
    return StructurePhase(config)
