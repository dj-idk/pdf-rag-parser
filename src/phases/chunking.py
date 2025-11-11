import logging
import re
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """Represents a single text chunk."""

    content: str
    chunk_id: int
    source_page: int
    source_chapter: Optional[str] = None
    source_section: Optional[str] = None
    char_count: int = 0
    word_count: int = 0
    sentence_count: int = 0

    def __post_init__(self):
        """Calculate metrics if not set."""
        if self.char_count == 0:
            self.char_count = len(self.content)
        if self.word_count == 0:
            self.word_count = len(self.content.split())
        if self.sentence_count == 0:
            self.sentence_count = self._count_sentences()

    def _count_sentences(self) -> int:
        """Count approximate number of sentences."""
        # Simple sentence counting: split by . ! ?
        sentences = re.split(r"[.!?]+", self.content)
        return len([s for s in sentences if s.strip()])


@dataclass
class ChunkingMetadata:
    """Metadata about the chunking process."""

    total_chunks: int
    total_characters: int
    total_words: int
    avg_chunk_size: float
    min_chunk_size: int
    max_chunk_size: int
    chunks_by_split_method: Dict[str, int]
    chunking_timestamp: str


class SmartChunker:
    """Implements smart semantic chunking algorithm."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the smart chunker.

        Args:
            config: Configuration dictionary with chunking settings
        """
        self.config = config or {}
        self.max_chunk_size = self.config.get("max_chunk_size", 800)
        self.chunk_overlap = self.config.get("chunk_overlap", 0)
        self.split_by_paragraph = self.config.get("split_by_paragraph", True)
        self.split_by_sentence = self.config.get("split_by_sentence", True)
        self.split_by_word = self.config.get("split_by_word", True)

        # Track split methods used
        self.split_methods = {
            "paragraph": 0,
            "sentence": 0,
            "word": 0,
            "oversized": 0,
        }

    def chunk(
        self, text_blocks: List[Dict[str, Any]]
    ) -> Tuple[List[TextChunk], ChunkingMetadata]:
        """
        Split text blocks into semantic chunks.

        Args:
            text_blocks: List of cleaned text blocks with structure info

        Returns:
            Tuple of (chunks, metadata)
        """
        logger.info(f"Starting smart chunking with max size: {self.max_chunk_size}")

        chunks = []
        chunk_id = 0
        total_characters = 0
        total_words = 0

        # Reset split method counters
        self.split_methods = {
            "paragraph": 0,
            "sentence": 0,
            "word": 0,
            "oversized": 0,
        }

        for block in text_blocks:
            content = block.get("content", "")
            page_num = block.get("page_num", 0)
            chapter = block.get("chapter", None)
            section = block.get("section", None)

            if not content.strip():
                continue

            # Split block into chunks
            block_chunks = self._chunk_block(content, page_num, chapter, section)

            for chunk_content in block_chunks:
                chunk = TextChunk(
                    content=chunk_content,
                    chunk_id=chunk_id,
                    source_page=page_num,
                    source_chapter=chapter,
                    source_section=section,
                )

                chunks.append(chunk)
                total_characters += chunk.char_count
                total_words += chunk.word_count
                chunk_id += 1

        # Calculate metadata
        avg_chunk_size = total_characters / len(chunks) if chunks else 0
        min_chunk_size = min(chunk.char_count for chunk in chunks) if chunks else 0
        max_chunk_size = max(chunk.char_count for chunk in chunks) if chunks else 0

        metadata = ChunkingMetadata(
            total_chunks=len(chunks),
            total_characters=total_characters,
            total_words=total_words,
            avg_chunk_size=avg_chunk_size,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
            chunks_by_split_method=self.split_methods,
            chunking_timestamp=self._get_timestamp(),
        )

        logger.info(
            f"Chunking complete: {len(chunks)} chunks created, "
            f"avg size: {avg_chunk_size:.0f} chars"
        )
        logger.info(f"Split methods: {self.split_methods}")

        return chunks, metadata

    def _chunk_block(
        self,
        content: str,
        page_num: int,
        chapter: Optional[str],
        section: Optional[str],
    ) -> List[str]:
        """
        Split a single text block into chunks using smart algorithm.

        Args:
            content: Text content to chunk
            page_num: Source page number
            chapter: Source chapter
            section: Source section

        Returns:
            List of chunk strings
        """
        # If content is within limit, return as-is
        if len(content) <= self.max_chunk_size:
            self.split_methods["paragraph"] += 1
            return [content]

        chunks = []

        # Step 1: Try splitting by paragraphs
        if self.split_by_paragraph:
            paragraphs = content.split("\n\n")
            current_chunk = ""

            for paragraph in paragraphs:
                paragraph = paragraph.strip()
                if not paragraph:
                    continue

                # Check if adding this paragraph exceeds limit
                test_chunk = (
                    current_chunk + "\n\n" + paragraph if current_chunk else paragraph
                )

                if len(test_chunk) <= self.max_chunk_size:
                    current_chunk = test_chunk
                else:
                    # Save current chunk if it has content
                    if current_chunk:
                        chunks.append(current_chunk)
                        self.split_methods["paragraph"] += 1

                    # Handle oversized paragraph
                    if len(paragraph) > self.max_chunk_size:
                        # Try splitting by sentences
                        paragraph_chunks = self._split_by_sentences(paragraph)
                        chunks.extend(paragraph_chunks)
                    else:
                        current_chunk = paragraph

            # Don't forget the last chunk
            if current_chunk:
                chunks.append(current_chunk)
                self.split_methods["paragraph"] += 1

        else:
            # If not splitting by paragraph, treat whole content as one unit
            chunks = self._split_by_sentences(content)

        return chunks

    def _split_by_sentences(self, text: str) -> List[str]:
        """
        Split text by sentences.

        Args:
            text: Text to split

        Returns:
            List of sentence-based chunks
        """
        # Split by sentence boundaries: . ! ? followed by space
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            test_chunk = current_chunk + " " + sentence if current_chunk else sentence

            if len(test_chunk) <= self.max_chunk_size:
                current_chunk = test_chunk
            else:
                # Save current chunk
                if current_chunk:
                    chunks.append(current_chunk)
                    self.split_methods["sentence"] += 1

                # Handle oversized sentence
                if len(sentence) > self.max_chunk_size:
                    word_chunks = self._split_by_words(sentence)
                    chunks.extend(word_chunks)
                else:
                    current_chunk = sentence

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)
            self.split_methods["sentence"] += 1

        return chunks

    def _split_by_words(self, text: str) -> List[str]:
        """
        Split text by words (last resort).

        Args:
            text: Text to split

        Returns:
            List of word-based chunks
        """
        words = text.split()
        chunks = []
        current_chunk = ""

        for word in words:
            test_chunk = current_chunk + " " + word if current_chunk else word

            if len(test_chunk) <= self.max_chunk_size:
                current_chunk = test_chunk
            else:
                # Save current chunk
                if current_chunk:
                    chunks.append(current_chunk)
                    self.split_methods["word"] += 1

                # If single word exceeds limit, force it
                if len(word) > self.max_chunk_size:
                    chunks.append(word)
                    self.split_methods["oversized"] += 1
                else:
                    current_chunk = word

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)
            self.split_methods["word"] += 1

        return chunks

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO format."""
        return datetime.now().isoformat()


class ChunkingPhase:
    """Orchestrates the chunking phase of the pipeline."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the chunking phase.

        Args:
            config: Configuration dictionary with chunking settings
        """
        self.config = config or {}
        self.chunker = SmartChunker(self.config)

    def run(
        self, text_blocks: List[Dict[str, Any]]
    ) -> Tuple[List[TextChunk], ChunkingMetadata]:
        """
        Run the chunking phase.

        Args:
            text_blocks: List of cleaned text blocks with structure info

        Returns:
            Tuple of (chunks, metadata)
        """
        logger.info("Starting chunking phase")

        chunks, metadata = self.chunker.chunk(text_blocks)

        logger.info(f"Chunking phase complete: {metadata.total_chunks} chunks created")

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
        report = {
            "total_chunks": metadata.total_chunks,
            "total_characters": metadata.total_characters,
            "total_words": metadata.total_words,
            "avg_chunk_size": round(metadata.avg_chunk_size, 2),
            "min_chunk_size": metadata.min_chunk_size,
            "max_chunk_size": metadata.max_chunk_size,
            "chunks_by_split_method": metadata.chunks_by_split_method,
            "chunking_timestamp": metadata.chunking_timestamp,
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Chunking report saved to: {output_path}")

    def save_chunks(self, chunks: List[TextChunk], output_path: str) -> None:
        """
        Save chunks to a JSON file.

        Args:
            chunks: List of text chunks
            output_path: Path to save the chunks
        """
        chunks_data = [
            {
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "source_page": chunk.source_page,
                "source_chapter": chunk.source_chapter,
                "source_section": chunk.source_section,
                "char_count": chunk.char_count,
                "word_count": chunk.word_count,
                "sentence_count": chunk.sentence_count,
            }
            for chunk in chunks
        ]

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Chunks saved to: {output_path}")
