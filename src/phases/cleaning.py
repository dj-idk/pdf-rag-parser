import logging
import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from src.phases.extraction import TextBlock


logger = logging.getLogger(__name__)


@dataclass
class CleaningMetadata:
    """Metadata about the cleaning process."""

    total_blocks_before: int = 0
    total_blocks_after: int = 0
    blocks_removed: int = 0
    characters_before: int = 0
    characters_after: int = 0
    characters_removed: int = 0
    sections_filtered: int = 0
    patterns_matched: int = 0
    pages_excluded: int = 0


class CleaningPhase:
    """
    Phase 3: Cleaning & Filtering

    Removes noise and unwanted sections from text blocks:
    - Page numbers and headers/footers
    - Unwanted sections (Index, Bibliography, etc.)
    - Excessive whitespace
    - Patterns matching regex rules
    - Content from excluded pages
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize cleaning phase.

        Args:
            config: Cleaning configuration dictionary
        """
        self.exclude_sections = config.get(
            "exclude_sections",
            ["Index", "Bibliography", "Appendix", "References"],
        )
        self.exclude_patterns = config.get(
            "exclude_patterns", [r"[Pp]age \d+", r"^\s*$", r"^\s*-{3,}\s*$"]
        )
        self.exclude_pages = config.get("exclude_pages", [])
        self.crop_top_percent = config.get("crop_top_percent", 0.0)
        self.crop_bottom_percent = config.get("crop_bottom_percent", 5.0)
        self.crop_left_percent = config.get("crop_left_percent", 0.0)
        self.crop_right_percent = config.get("crop_right_percent", 0.0)

        # Compile regex patterns for efficiency
        self.compiled_patterns = []
        for pattern in self.exclude_patterns:
            try:
                self.compiled_patterns.append(re.compile(pattern))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")

        logger.info("Cleaning phase initialized")
        logger.debug(f"  Exclude sections: {self.exclude_sections}")
        logger.debug(f"  Exclude patterns: {len(self.compiled_patterns)} compiled")
        logger.debug(f"  Exclude pages: {self.exclude_pages}")
        logger.debug(
            f"  Crop: top={self.crop_top_percent}%, bottom={self.crop_bottom_percent}%"
        )

    def run(
        self, text_blocks: List[TextBlock], structure_metadata: Dict[str, Any]
    ) -> Tuple[List[TextBlock], CleaningMetadata]:
        """
        Run the cleaning phase.

        Args:
            text_blocks: List of text blocks from extraction phase
            structure_metadata: Metadata from structure analysis phase

        Returns:
            Tuple of (cleaned_blocks, cleaning_metadata)
        """
        logger.info("Starting cleaning phase...")

        metadata = CleaningMetadata()
        metadata.total_blocks_before = len(text_blocks)
        metadata.characters_before = sum(
            len(self._get_block_text(block)) for block in text_blocks
        )

        cleaned_blocks = []

        for block in text_blocks:
            # Step 1: Filter by excluded pages
            if self._should_exclude_page(block):
                metadata.pages_excluded += 1
                continue

            # Step 2: Filter by excluded sections
            if self._should_exclude_section(block):
                metadata.sections_filtered += 1
                continue

            # Step 3: Apply positional filtering (cropping)
            cleaned_text = self._apply_positional_filtering(block)
            if not cleaned_text or not cleaned_text.strip():
                continue

            # Step 4: Apply regex pattern filtering
            cleaned_text, patterns_matched = self._apply_regex_filtering(cleaned_text)
            metadata.patterns_matched += patterns_matched

            if not cleaned_text or not cleaned_text.strip():
                continue

            # Step 5: Clean excessive whitespace
            cleaned_text = self._clean_whitespace(cleaned_text)

            if not cleaned_text or not cleaned_text.strip():
                continue

            # Create new block with cleaned text
            cleaned_block = self._create_cleaned_block(block, cleaned_text)
            cleaned_blocks.append(cleaned_block)

        metadata.total_blocks_after = len(cleaned_blocks)
        metadata.blocks_removed = (
            metadata.total_blocks_before - metadata.total_blocks_after
        )
        metadata.characters_after = sum(
            len(self._get_block_text(block)) for block in cleaned_blocks
        )
        metadata.characters_removed = (
            metadata.characters_before - metadata.characters_after
        )

        logger.info(f"✓ Cleaning complete")
        logger.info(f"  Blocks before: {metadata.total_blocks_before}")
        logger.info(f"  Blocks after: {metadata.total_blocks_after}")
        logger.info(f"  Blocks removed: {metadata.blocks_removed}")
        logger.info(f"  Characters before: {metadata.characters_before}")
        logger.info(f"  Characters after: {metadata.characters_after}")
        logger.info(f"  Characters removed: {metadata.characters_removed}")
        logger.info(f"  Sections filtered: {metadata.sections_filtered}")
        logger.info(f"  Patterns matched: {metadata.patterns_matched}")
        logger.info(f"  Pages excluded: {metadata.pages_excluded}")

        return cleaned_blocks, asdict(metadata)

    def _get_block_text(self, block: Any) -> str:
        """
        Get text content from a block, handling different block types.

        Args:
            block: Text block (TextBlock or StructuredTextBlock)

        Returns:
            Text content
        """
        if hasattr(block, "text"):
            return block.text
        elif hasattr(block, "content"):
            return block.content
        else:
            return ""

    def _create_cleaned_block(self, original_block: Any, cleaned_text: str) -> Any:
        """
        Create a cleaned block preserving original attributes.

        Args:
            original_block: Original block object
            cleaned_text: Cleaned text content

        Returns:
            New block with cleaned text
        """
        # Create a copy of the block with updated text
        if hasattr(original_block, "__dataclass_fields__"):
            # It's a dataclass, use asdict and reconstruct
            block_dict = asdict(original_block)
            if "text" in block_dict:
                block_dict["text"] = cleaned_text
            elif "content" in block_dict:
                block_dict["content"] = cleaned_text
            return type(original_block)(**block_dict)
        else:
            # Fallback: try to set text attribute
            original_block.text = cleaned_text
            return original_block

    def _should_exclude_page(self, block: Any) -> bool:
        """
        Check if block should be excluded based on page number.

        Args:
            block: Text block to check

        Returns:
            True if block should be excluded
        """
        if not self.exclude_pages:
            return False

        page_num = getattr(block, "page_number", None) or getattr(
            block, "page_num", None
        )
        return page_num in self.exclude_pages if page_num else False

    def _should_exclude_section(self, block: Any) -> bool:
        """
        Check if block should be excluded based on section title.

        Args:
            block: Text block to check

        Returns:
            True if block should be excluded
        """
        section_title = getattr(block, "section_title", None)
        if not section_title:
            return False

        for excluded_section in self.exclude_sections:
            if excluded_section.lower() in section_title.lower():
                return True

        return False

    def _apply_positional_filtering(self, block: Any) -> str:
        """
        Apply positional filtering based on crop percentages.

        This removes content from specified areas of the page
        (e.g., headers, footers).

        Args:
            block: Text block to filter

        Returns:
            Filtered text (may be empty if entirely in crop zone)
        """
        bbox = getattr(block, "bbox", None)
        if not bbox:
            return self._get_block_text(block)

        # Extract bbox coordinates (x0, y0, x1, y1)
        x0, y0, x1, y1 = bbox

        # Calculate page dimensions (assuming standard page)
        page_width = x1 - x0
        page_height = y1 - y0

        # Calculate crop boundaries
        crop_top = page_height * (self.crop_top_percent / 100.0)
        crop_bottom = page_height * (1.0 - self.crop_bottom_percent / 100.0)
        crop_left = page_width * (self.crop_left_percent / 100.0)
        crop_right = page_width * (1.0 - self.crop_right_percent / 100.0)

        # Check if block is entirely in crop zone
        if y0 < crop_top or y1 > crop_bottom or x0 < crop_left or x1 > crop_right:
            # Block is in crop zone, exclude it
            return ""

        return self._get_block_text(block)

    def _apply_regex_filtering(self, text: str) -> Tuple[str, int]:
        """
        Apply regex pattern filtering to remove matching content.

        Args:
            text: Text to filter

        Returns:
            Tuple of (filtered_text, number_of_patterns_matched)
        """
        patterns_matched = 0
        filtered_text = text

        for pattern in self.compiled_patterns:
            matches = pattern.findall(filtered_text)
            if matches:
                patterns_matched += len(matches)
                filtered_text = pattern.sub("", filtered_text)

        return filtered_text, patterns_matched

    def _clean_whitespace(self, text: str) -> str:
        """
        Clean excessive whitespace from text.

        - Remove leading/trailing whitespace
        - Replace multiple blank lines with single blank line
        - Replace multiple spaces with single space

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        # Replace multiple blank lines with single blank line
        text = re.sub(r"\n\s*\n+", "\n\n", text)

        # Replace multiple spaces with single space
        text = re.sub(r" +", " ", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    def save_cleaning_report(self, metadata: Dict[str, Any], output_path: str) -> None:
        """
        Save cleaning report to JSON file.

        Args:
            metadata: Cleaning metadata dictionary
            output_path: Path to save report
        """
        import json
        from pathlib import Path

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "cleaning_config": {
                "exclude_sections": self.exclude_sections,
                "exclude_patterns": self.exclude_patterns,
                "exclude_pages": self.exclude_pages,
                "crop_top_percent": self.crop_top_percent,
                "crop_bottom_percent": self.crop_bottom_percent,
                "crop_left_percent": self.crop_left_percent,
                "crop_right_percent": self.crop_right_percent,
            },
            "metadata": metadata,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Cleaning report saved to: {output_path}")
