"""
Phase 3: Smart Chunking
Splits cleaned text into semantic chunks respecting boundaries.
"""

import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a semantic chunk of text."""

    content: str
    chunk_num: int
    source_page: int
    source_chapter: Optional[str] = None
    source_part: Optional[str] = None
    char_count: int = 0

    def __post_init__(self):
        if self.char_count == 0:
            self.char_count = len(self.content)


@dataclass
class ChunkingMetadata:
    """Metadata from chunking phase."""

    total_chunks: int
    total_characters: int
    avg_chunk_size: float
    min_chunk_size: int
    max_chunk_size: int


class TextChunker:
    """Handles intelligent text chunking."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the text chunker.

        Args:
            config: Configuration dictionary with chunking settings
        """
        self.config = config or {}
        self.max_chunk_size = self.config.get("max_chunk_size", 800)
        self.chunk_overlap = self.config.get("chunk_overlap", 0)
        self.split_by_paragraph = self.config.get("split_by_paragraph", True)
        self.split_by_sentence = self.config.get("split_by_sentence", True)
        self.split_by_word = self.config.get("split_by_word", True)

    def run(
        self, text_blocks: List[Any], chapters_config: Optional[List[Dict]] = None
    ) -> tuple[List[Chunk], ChunkingMetadata]:
        """
        Run the chunking phase on cleaned text blocks.

        Args:
            text_blocks: List of cleaned TextBlock objects
            chapters_config: Optional list of chapter configurations

        Returns:
            Tuple of (chunks, metadata)
        """
        logger.info(f"Starting chunking phase on {len(text_blocks)} blocks")

        chunks = []
        chunk_num = 1

        # Build chapter mapping for quick lookup
        chapter_map = self._build_chapter_map(chapters_config)

        # Group blocks by chapter to maintain semantic coherence
        block_groups = self._group_blocks_by_chapter(text_blocks, chapter_map)

        for group_blocks in block_groups:
            # Combine blocks within group into semantic chunks
            group_chunks = self._create_chunks_from_group(
                group_blocks, chapter_map, chunk_num
            )
            chunks.extend(group_chunks)
            chunk_num += len(group_chunks)

        # Calculate metadata
        total_chars = sum(chunk.char_count for chunk in chunks)
        avg_size = total_chars / len(chunks) if chunks else 0
        min_size = min(chunk.char_count for chunk in chunks) if chunks else 0
        max_size = max(chunk.char_count for chunk in chunks) if chunks else 0

        metadata = ChunkingMetadata(
            total_chunks=len(chunks),
            total_characters=total_chars,
            avg_chunk_size=avg_size,
            min_chunk_size=min_size,
            max_chunk_size=max_size,
        )

        logger.info(
            f"Chunking complete: {len(chunks)} chunks created "
            f"(avg size: {avg_size:.0f} chars)"
        )

        return chunks, metadata

    def _build_chapter_map(
        self, chapters_config: Optional[List[Dict]]
    ) -> Dict[int, Dict]:
        """Build a map of page numbers to chapter info."""
        chapter_map = {}

        if not chapters_config:
            return chapter_map

        for chapter in chapters_config:
            # Convert dataclass to dict if needed
            if hasattr(chapter, "__dataclass_fields__"):
                chapter = asdict(chapter)

            start_page = chapter.get("start_page", 0)
            end_page = chapter.get("end_page", 0)
            chapter_name = chapter.get("name", "Unknown")
            part_name = chapter.get("part", "Unknown")

            for page_num in range(start_page, end_page + 1):
                chapter_map[page_num] = {
                    "chapter": chapter_name,
                    "part": part_name,
                }

        return chapter_map

    def _get_chapter_info(self, page_num: int, chapter_map: Dict) -> Dict:
        """Get chapter info for a given page number."""
        return chapter_map.get(page_num, {"chapter": "Unknown", "part": "Unknown"})

    def _group_blocks_by_chapter(
        self, text_blocks: List[Any], chapter_map: Dict
    ) -> List[List[Any]]:
        """Group blocks by chapter to maintain semantic coherence."""
        if not chapter_map:
            # If no chapter info, group all blocks together
            return [text_blocks]

        groups = []
        current_group = []
        current_chapter = None

        for block in text_blocks:
            chapter_info = self._get_chapter_info(block.page_num, chapter_map)
            block_chapter = chapter_info.get("chapter", "Unknown")

            if current_chapter is None:
                current_chapter = block_chapter
                current_group.append(block)
            elif block_chapter == current_chapter:
                current_group.append(block)
            else:
                # Chapter changed, save group and start new one
                if current_group:
                    groups.append(current_group)
                current_group = [block]
                current_chapter = block_chapter

        # Add final group
        if current_group:
            groups.append(current_group)

        return groups

    def _create_chunks_from_group(
        self, group_blocks: List[Any], chapter_map: Dict, start_chunk_num: int
    ) -> List[Chunk]:
        """Create semantic chunks by combining blocks within a group."""
        chunks = []
        chunk_num = start_chunk_num
        current_chunk_content = ""
        current_chunk_page = group_blocks[0].page_num if group_blocks else 1
        current_chapter_info = None

        for block in group_blocks:
            chapter_info = self._get_chapter_info(block.page_num, chapter_map)

            # Update chapter info on first block or when it changes
            if current_chapter_info is None:
                current_chapter_info = chapter_info
                current_chunk_page = block.page_num

            block_content = block.content.strip()

            # Skip empty or whitespace-only blocks
            if not block_content:
                continue

            # Check if adding this block would exceed max chunk size
            potential_size = len(current_chunk_content) + len(block_content) + 2

            if potential_size <= self.max_chunk_size:
                # Add to current chunk
                if current_chunk_content:
                    current_chunk_content += "\n\n"
                current_chunk_content += block_content
            else:
                # Current chunk is full, save it
                if current_chunk_content:
                    chunk = Chunk(
                        content=current_chunk_content,
                        chunk_num=chunk_num,
                        source_page=current_chunk_page,
                        source_chapter=current_chapter_info.get("chapter"),
                        source_part=current_chapter_info.get("part"),
                    )
                    chunks.append(chunk)
                    chunk_num += 1

                # Handle oversized block
                if len(block_content) <= self.max_chunk_size:
                    # Block fits in new chunk
                    current_chunk_content = block_content
                    current_chunk_page = block.page_num
                else:
                    # Block is too large, split it
                    split_chunks = self._chunk_text(block_content)
                    for split_content in split_chunks:
                        chunk = Chunk(
                            content=split_content,
                            chunk_num=chunk_num,
                            source_page=block.page_num,
                            source_chapter=chapter_info.get("chapter"),
                            source_part=chapter_info.get("part"),
                        )
                        chunks.append(chunk)
                        chunk_num += 1
                    current_chunk_content = ""

        # Add final chunk
        if current_chunk_content:
            chunk = Chunk(
                content=current_chunk_content,
                chunk_num=chunk_num,
                source_page=current_chunk_page,
                source_chapter=(
                    current_chapter_info.get("chapter")
                    if current_chapter_info
                    else "Unknown"
                ),
                source_part=(
                    current_chapter_info.get("part")
                    if current_chapter_info
                    else "Unknown"
                ),
            )
            chunks.append(chunk)

        return chunks

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split oversized text into semantic chunks.

        Algorithm:
        1. Try splitting by paragraphs
        2. If paragraph > max_size, try splitting by sentences
        3. If sentence > max_size, split by words
        """
        chunks = []

        if not text or len(text) <= self.max_chunk_size:
            return [text] if text else []

        # Split by paragraphs
        if self.split_by_paragraph:
            paragraphs = text.split("\n\n")
        else:
            paragraphs = [text]

        current_chunk = ""

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # Check if adding this paragraph exceeds limit
            if len(current_chunk) + len(paragraph) + 2 <= self.max_chunk_size:
                if current_chunk:
                    current_chunk += "\n\n"
                current_chunk += paragraph
            else:
                # Save current chunk if not empty
                if current_chunk:
                    chunks.append(current_chunk)

                # Handle oversized paragraph
                if len(paragraph) <= self.max_chunk_size:
                    current_chunk = paragraph
                else:
                    # Paragraph is oversized, split it and add all parts to chunks
                    # Reset current_chunk as we are handling this paragraph separately
                    current_chunk = ""

                    # Split paragraph by sentences
                    if self.split_by_sentence:
                        sentences = self._split_by_sentences(paragraph)
                    else:
                        sentences = [paragraph]

                    para_chunk = ""
                    for sentence in sentences:
                        if len(para_chunk) + len(sentence) + 1 <= self.max_chunk_size:
                            if para_chunk:
                                para_chunk += " "
                            para_chunk += sentence
                        else:
                            # Save current sentence chunk if not empty
                            if para_chunk:
                                chunks.append(para_chunk)

                            # Handle oversized sentence
                            if len(sentence) <= self.max_chunk_size:
                                para_chunk = sentence
                            else:
                                # Split by words (last resort)
                                if self.split_by_word:
                                    word_chunks = self._split_by_words(sentence)
                                    chunks.extend(word_chunks)
                                    para_chunk = ""
                                else:
                                    # Can't split by word, so add the oversized sentence as-is
                                    chunks.append(sentence)
                                    para_chunk = ""

                    # Add the last remaining sentence chunk from the oversized paragraph
                    if para_chunk:
                        chunks.append(para_chunk)

        # Add the final remaining chunk (which may be built from paragraphs)
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _split_by_sentences(self, text: str) -> List[str]:
        """Split text by sentence boundaries."""
        # Simple sentence splitting (can be improved with NLTK)
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _split_by_words(self, text: str) -> List[str]:
        """Split text by words when it exceeds max chunk size."""
        words = text.split()
        chunks = []
        current_chunk = ""

        for word in words:
            if len(current_chunk) + len(word) + 1 <= self.max_chunk_size:
                if current_chunk:
                    current_chunk += " "
                current_chunk += word
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = word

        if current_chunk:
            chunks.append(current_chunk)

        return chunks


class ChunkingPhase:
    """Orchestrates the chunking phase of the pipeline."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the chunking phase.

        Args:
            config: Configuration dictionary with chunking settings
        """
        self.config = config or {}
        self.chunker = TextChunker(self.config)

    def run(
        self, text_blocks: List[Any], chapters_config: Optional[List[Dict]] = None
    ) -> tuple[List[Chunk], ChunkingMetadata]:
        """
        Run the chunking phase on cleaned text blocks.

        Args:
            text_blocks: List of cleaned TextBlock objects
            chapters_config: Optional list of chapter configurations

        Returns:
            Tuple of (chunks, metadata)
        """
        logger.info("Starting chunking phase")

        chunks, metadata = self.chunker.run(text_blocks, chapters_config)

        logger.info("Chunking phase complete")

        return chunks, metadata

    def save_chunking_report(
        self, metadata: ChunkingMetadata, output_path: str
    ) -> None:
        """
        Save chunking metadata to a JSON report.

        Args:
            metadata: Chunking metadata
            output_path: Path to save the report
        """
        import json
        from pathlib import Path

        report = {
            "total_chunks": metadata.total_chunks,
            "total_characters": metadata.total_characters,
            "avg_chunk_size": metadata.avg_chunk_size,
            "min_chunk_size": metadata.min_chunk_size,
            "max_chunk_size": metadata.max_chunk_size,
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Chunking report saved to: {output_path}")


def create_chunker(config: Optional[Dict] = None) -> ChunkingPhase:
    """
    Factory function to create a chunking phase instance.

    Args:
        config: Configuration dictionary

    Returns:
        ChunkingPhase instance
    """
    return ChunkingPhase(config)
