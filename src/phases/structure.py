from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class TextBlockType(Enum):
    """Classification of text block types."""

    PART_HEADING = "PART_HEADING"
    CHAPTER_HEADING = "CHAPTER_HEADING"
    BODY_TEXT = "BODY_TEXT"


@dataclass
class StructuredTextBlock:
    """Text block with structural classification."""

    content: str
    page_num: int
    block_type: TextBlockType
    hierarchy_level: int = 0
    parent_heading: Optional[str] = None


@dataclass
class StructureMetadata:
    """Metadata about the structure analysis."""

    total_blocks: int
    classified_blocks: int
    parts_found: int
    chapters_found: int
    structure_method: str
    analysis_timestamp: str


class StructurePhase:
    """Analyzes document structure using regex patterns for Persian text."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize structure analysis phase."""
        self.config = config or {}
        self.part_pattern = self.config.get(
            "part_pattern", r"^(فصل)\s+([۰-۹]+|[الف-ی]+)\s*[:]*\s*(.*)$"
        )
        self.chapter_pattern = self.config.get(
            "chapter_pattern", r"^(درس)\s+([۰-۹]+)\s*[:]*\s*(.*)$"
        )

    def run(
        self,
        text_blocks: List[Dict[str, Any]],
        extraction_metadata: Optional[Dict] = None,
    ) -> Tuple[List[StructuredTextBlock], StructureMetadata]:
        """Run structure analysis phase."""
        logger.info("Starting structure analysis phase")

        structured_blocks = []
        current_part = None
        current_chapter = None
        parts_count = 0
        chapters_count = 0

        for block in text_blocks:
            content = block.get("content", "").strip()
            if not content:
                continue

            # Check if it's a part heading
            part_match = re.match(self.part_pattern, content, re.UNICODE)
            if part_match:
                current_part = content
                current_chapter = None
                parts_count += 1
                block_type = TextBlockType.PART_HEADING
                hierarchy_level = 0
                parent_heading = None
            # Check if it's a chapter heading
            elif re.match(self.chapter_pattern, content, re.UNICODE):
                current_chapter = content
                chapters_count += 1
                block_type = TextBlockType.CHAPTER_HEADING
                hierarchy_level = 1
                parent_heading = current_part
            # Otherwise it's body text
            else:
                block_type = TextBlockType.BODY_TEXT
                hierarchy_level = 2
                parent_heading = current_chapter or current_part

            structured_block = StructuredTextBlock(
                content=content,
                page_num=block.get("page_num", 0),
                block_type=block_type,
                hierarchy_level=hierarchy_level,
                parent_heading=parent_heading,
            )
            structured_blocks.append(structured_block)

        metadata = StructureMetadata(
            total_blocks=len(text_blocks),
            classified_blocks=parts_count + chapters_count,
            parts_found=parts_count,
            chapters_found=chapters_count,
            structure_method="regex",
            analysis_timestamp=datetime.now().isoformat(),
        )

        logger.info(
            f"Structure analysis complete: {parts_count} parts, {chapters_count} chapters"
        )

        return structured_blocks, metadata
