"""
Phase 2: Cleaning & Filtering
Removes noise, unwanted sections, and prepares text for chunking.
"""

import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CleaningMetadata:
    """Metadata from cleaning phase."""

    total_blocks_input: int
    total_blocks_output: int
    total_characters_input: int
    total_characters_output: int
    blocks_removed: int
    characters_removed: int


class TextCleaner:
    """Handles text cleaning and filtering."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the text cleaner.

        Args:
            config: Configuration dictionary with cleaning settings
        """
        self.config = config or {}
        self.exclude_sections = self.config.get("exclude_sections", [])
        self.exclude_exact_blocks = self.config.get("exclude_exact_blocks", [])
        self.exclude_patterns = self.config.get("exclude_patterns", [])
        self.exclude_pages = self.config.get("exclude_pages", [])
        self.crop_top_percent = self.config.get("crop_top_percent", 0.0)
        self.crop_bottom_percent = self.config.get("crop_bottom_percent", 5.0)
        self.crop_left_percent = self.config.get("crop_left_percent", 0.0)
        self.crop_right_percent = self.config.get("crop_right_percent", 0.0)

        # Compile regex patterns for efficiency
        self.compiled_patterns = []
        for pattern in self.exclude_patterns:
            try:
                self.compiled_patterns.append(re.compile(pattern))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")

    def run(self, text_blocks: List[Any]) -> tuple[List[Any], CleaningMetadata]:
        """
        Run the cleaning phase on extracted text blocks.

        Args:
            text_blocks: List of TextBlock objects from extraction phase

        Returns:
            Tuple of (cleaned_blocks, metadata)
        """
        logger.info(f"Starting cleaning phase on {len(text_blocks)} blocks")

        total_chars_input = sum(block.char_count for block in text_blocks)
        cleaned_blocks = []

        for block in text_blocks:
            # Skip excluded pages
            if block.page_num in self.exclude_pages:
                logger.debug(f"Skipping block on excluded page {block.page_num}")
                continue

            # Skip blocks in excluded sections
            if self._is_excluded_section(block.content):
                logger.debug(f"Skipping excluded section: {block.content[:50]}")
                continue

            # Skip blocks matching exclude patterns
            if self._matches_exclude_pattern(block.content):
                logger.debug(f"Skipping pattern match: {block.content[:50]}")
                continue

            # Skip blocks in cropped areas
            if self._is_in_cropped_area(block):
                logger.debug(f"Skipping block in cropped area")
                continue

            # Clean the content
            cleaned_content = self._clean_content(block.content)

            if cleaned_content:  # Only keep non-empty blocks
                block.content = cleaned_content
                block.char_count = len(cleaned_content)
                cleaned_blocks.append(block)

        total_chars_output = sum(block.char_count for block in cleaned_blocks)

        metadata = CleaningMetadata(
            total_blocks_input=len(text_blocks),
            total_blocks_output=len(cleaned_blocks),
            total_characters_input=total_chars_input,
            total_characters_output=total_chars_output,
            blocks_removed=len(text_blocks) - len(cleaned_blocks),
            characters_removed=total_chars_input - total_chars_output,
        )

        logger.info(
            f"Cleaning complete: {len(cleaned_blocks)} blocks remaining "
            f"({metadata.blocks_removed} removed, "
            f"{metadata.characters_removed} characters removed)"
        )

        return cleaned_blocks, metadata

    def _is_excluded_section(self, content: str) -> bool:
        """Check if content matches any excluded section title."""
        cleaned_content = content.strip()

        # Check exact block matches first
        for section in self.exclude_exact_blocks:
            if section.lower() == cleaned_content.lower():
                return True

        # Then check partial matches
        for section in self.exclude_sections:
            if section.lower() in cleaned_content.lower():
                return True

        return False

    def _matches_exclude_pattern(self, content: str) -> bool:
        """Check if content matches any exclude regex pattern."""
        for pattern in self.compiled_patterns:
            if pattern.search(content):
                return True
        return False

    def _is_in_cropped_area(self, block: Any) -> bool:
        """Check if block is in a cropped area based on position."""
        # Get page dimensions (approximate)
        page_height = 792  # Standard letter height in points
        page_width = 612  # Standard letter width in points

        # Calculate crop boundaries
        top_boundary = page_height * (self.crop_top_percent / 100)
        bottom_boundary = page_height * (1 - self.crop_bottom_percent / 100)
        left_boundary = page_width * (self.crop_left_percent / 100)
        right_boundary = page_width * (1 - self.crop_right_percent / 100)

        # Check if block is outside boundaries
        if block.y0 < top_boundary or block.y1 > bottom_boundary:
            return True
        if block.x0 < left_boundary or block.x1 > right_boundary:
            return True

        return False

    def _clean_content(self, content: str) -> str:
        """Clean individual text content."""
        # Remove extra whitespace (including newlines)
        content = re.sub(r"\s+", " ", content)
        content = content.strip()

        # Remove null bytes and control characters
        content = "".join(char for char in content if ord(char) >= 32)

        # Remove page numbers (English and Persian formats)
        # English: "Page 123", "page 123"
        content = re.sub(r"[Pp]age\s+\d+", "", content)
        # Standalone page numbers - Persian digits only (۰-۹)
        content = re.sub(r"^[\s۰-۹]+$", "", content)
        # Standalone page numbers - English digits only
        content = re.sub(r"^\s*\d+\s*$", "", content)

        # Clean up any resulting extra whitespace
        content = re.sub(r"\s+", " ", content)
        content = content.strip()

        return content


class CleaningPhase:
    """Orchestrates the cleaning phase of the pipeline."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the cleaning phase.

        Args:
            config: Configuration dictionary with cleaning settings
        """
        self.config = config or {}
        self.cleaner = TextCleaner(self.config)

    def run(self, text_blocks: List[Any]) -> tuple[List[Any], CleaningMetadata]:
        """
        Run the cleaning phase.

        Args:
            text_blocks: List of TextBlock objects from extraction phase

        Returns:
            Tuple of (cleaned_blocks, metadata)
        """
        logger.info("Starting cleaning phase")
        cleaned_blocks, metadata = self.cleaner.run(text_blocks)
        logger.info("Cleaning phase complete")
        return cleaned_blocks, metadata
