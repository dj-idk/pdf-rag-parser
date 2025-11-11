"""
Phase 4: File Organization & Output
Saves chunks in an organized folder structure with metadata.
"""

import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FileOrganizationMetadata:
    """Metadata for file organization phase."""

    total_chunks_saved: int = 0
    total_chapters: int = 0
    total_parts: int = 0
    folder_structure: Dict[str, Any] = None
    index_file_path: str = ""
    chunks_by_chapter: Dict[str, int] = None

    def __post_init__(self):
        if self.folder_structure is None:
            self.folder_structure = {}
        if self.chunks_by_chapter is None:
            self.chunks_by_chapter = {}


class FileOrganizer:
    """Handles file organization and output generation."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the file organizer.

        Args:
            config: Configuration dictionary with output settings
        """
        self.config = config or {}
        self.create_metadata = self.config.get("create_metadata", True)
        self.create_index = self.config.get("create_index", True)
        self.preserve_structure = self.config.get("preserve_structure", True)

    def run(
        self,
        chunks: List[Any],
        output_dir: str,
        chapters_config: Optional[List[Dict]] = None,
    ) -> FileOrganizationMetadata:
        """
        Run the file organization phase.

        Args:
            chunks: List of Chunk objects from chunking phase
            output_dir: Base output directory
            chapters_config: Optional list of chapter configurations

        Returns:
            FileOrganizationMetadata instance
        """
        logger.info(f"Organizing {len(chunks)} chunks into folder structure...")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Build folder structure
        folder_structure = self._build_folder_structure(chunks, chapters_config)

        # Save chunks to organized folders
        total_chunks_saved = self._save_chunks_to_folders(
            chunks, output_path, folder_structure
        )

        # Create metadata files for each chapter
        if self.create_metadata:
            self._create_chapter_metadata(chunks, output_path, folder_structure)

        # Create index file
        index_file_path = ""
        if self.create_index:
            index_file_path = self._create_index_file(
                chunks, output_path, folder_structure, chapters_config
            )

        metadata = FileOrganizationMetadata(
            total_chunks_saved=total_chunks_saved,
            total_chapters=len(self._get_all_chapters(folder_structure)),
            total_parts=len(folder_structure),
            folder_structure=folder_structure,
            index_file_path=index_file_path,
            chunks_by_chapter=self._count_chunks_by_chapter(chunks, folder_structure),
        )

        logger.info(f"✓ File organization complete")
        logger.info(f"  Chunks saved: {total_chunks_saved}")
        logger.info(f"  Chapters: {metadata.total_chapters}")
        logger.info(f"  Parts: {metadata.total_parts}")

        return metadata

    def _build_folder_structure(
        self,
        chunks: List[Any],
        chapters_config: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Build the folder structure from chunks and chapter config."""
        structure = {}

        if not chapters_config:
            # Build structure from chunks
            for chunk in chunks:
                part = chunk.source_part or "Unknown"
                chapter = chunk.source_chapter or "Unknown"

                if part not in structure:
                    structure[part] = {"chapters": {}}

                if chapter not in structure[part]["chapters"]:
                    structure[part]["chapters"][chapter] = []

                structure[part]["chapters"][chapter].append(chunk.chunk_num)
        else:
            # Build structure from config
            for chapter_config in chapters_config:
                # Convert dataclass to dict if needed
                if hasattr(chapter_config, "__dataclass_fields__"):
                    chapter_config = asdict(chapter_config)

                part = chapter_config.get("part", "Unknown")
                chapter = chapter_config.get("name", "Unknown")

                if part not in structure:
                    structure[part] = {"chapters": {}}

                if chapter not in structure[part]["chapters"]:
                    structure[part]["chapters"][chapter] = []

        return structure

    def _save_chunks_to_folders(
        self,
        chunks: List[Any],
        output_path: Path,
        folder_structure: Dict[str, Any],
    ) -> int:
        """Save chunks to organized folder structure."""
        total_saved = 0

        for chunk in chunks:
            part = chunk.source_part or "Unknown"
            chapter = chunk.source_chapter or "Unknown"

            # Sanitize folder names
            part_folder = self._sanitize_folder_name(part)
            chapter_folder = self._sanitize_folder_name(chapter)

            # Create folder path
            chapter_path = output_path / part_folder / chapter_folder
            chapter_path.mkdir(parents=True, exist_ok=True)

            # Save chunk file
            chunk_file = chapter_path / f"chunk_{chunk.chunk_num:04d}.txt"

            try:
                with open(chunk_file, "w", encoding="utf-8") as f:
                    f.write(chunk.content)
                total_saved += 1
            except Exception as e:
                logger.error(f"Failed to save chunk {chunk.chunk_num}: {e}")

        return total_saved

    def _create_chapter_metadata(
        self,
        chunks: List[Any],
        output_path: Path,
        folder_structure: Dict[str, Any],
    ) -> None:
        """Create metadata.json files for each chapter."""
        chapter_chunks = {}

        # Group chunks by chapter
        for chunk in chunks:
            chapter = chunk.source_chapter or "Unknown"
            if chapter not in chapter_chunks:
                chapter_chunks[chapter] = []
            chapter_chunks[chapter].append(chunk)

        # Create metadata for each chapter
        for part, part_data in folder_structure.items():
            part_folder = self._sanitize_folder_name(part)

            for chapter, chunk_nums in part_data["chapters"].items():
                chapter_folder = self._sanitize_folder_name(chapter)
                chapter_path = output_path / part_folder / chapter_folder

                # Get chunks for this chapter
                chapter_chunk_list = chapter_chunks.get(chapter, [])

                if not chapter_chunk_list:
                    continue

                # Calculate metadata
                total_chunks = len(chapter_chunk_list)
                total_characters = sum(c.char_count for c in chapter_chunk_list)
                source_pages = sorted(set(c.source_page for c in chapter_chunk_list))

                metadata = {
                    "chapter": chapter,
                    "part": part,
                    "total_chunks": total_chunks,
                    "total_characters": total_characters,
                    "source_pages": source_pages,
                }

                # Save metadata file
                metadata_file = chapter_path / "metadata.json"

                try:
                    with open(metadata_file, "w", encoding="utf-8") as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"Failed to save metadata for {chapter}: {e}")

    def _create_index_file(
        self,
        chunks: List[Any],
        output_path: Path,
        folder_structure: Dict[str, Any],
        chapters_config: Optional[List[Dict]] = None,
    ) -> str:
        """Create root index.json file."""
        total_characters = sum(chunk.char_count for chunk in chunks)

        # Build structure for index
        structure_data = []

        for part, part_data in folder_structure.items():
            part_entry = {"part": part, "chapters": []}

            for chapter, chunk_nums in part_data["chapters"].items():
                chapter_entry = {
                    "name": chapter,
                    "chunks": len(chunk_nums),
                    "path": f"{self._sanitize_folder_name(part)}/{self._sanitize_folder_name(chapter)}",
                }
                part_entry["chapters"].append(chapter_entry)

            structure_data.append(part_entry)

        index_data = {
            "source_pdf": "document.pdf",
            "total_chunks": len(chunks),
            "total_characters": total_characters,
            "total_parts": len(folder_structure),
            "total_chapters": len(self._get_all_chapters(folder_structure)),
            "structure": structure_data,
        }

        # Save index file
        index_file = output_path / "index.json"

        try:
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Index file created: {index_file}")
            return str(index_file)
        except Exception as e:
            logger.error(f"Failed to create index file: {e}")
            return ""

    def _sanitize_folder_name(self, name: str) -> str:
        """Convert folder name to safe format."""
        # Replace spaces with underscores
        sanitized = name.replace(" ", "_")
        # Remove special characters
        sanitized = "".join(c for c in sanitized if c.isalnum() or c in "_-")
        # Remove multiple underscores
        sanitized = "_".join(filter(None, sanitized.split("_")))

        return sanitized if sanitized else "Uncategorized"

    def _get_all_chapters(self, folder_structure: Dict[str, Any]) -> List[str]:
        """Get all chapter names from folder structure."""
        chapters = []
        for part_data in folder_structure.values():
            chapters.extend(part_data["chapters"].keys())
        return chapters

    def _count_chunks_by_chapter(
        self,
        chunks: List[Any],
        folder_structure: Dict[str, Any],
    ) -> Dict[str, int]:
        """Count chunks per chapter."""
        counts = {}
        for chunk in chunks:
            chapter = chunk.source_chapter or "Unknown"
            counts[chapter] = counts.get(chapter, 0) + 1
        return counts


class FileOrganizationPhase:
    """Orchestrates the file organization phase of the pipeline."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the file organization phase.

        Args:
            config: Configuration dictionary with output settings
        """
        self.config = config or {}
        self.organizer = FileOrganizer(self.config)

    def run(
        self,
        chunks: List[Any],
        output_dir: str,
        chapters_config: Optional[List[Dict]] = None,
    ) -> FileOrganizationMetadata:
        """
        Run the file organization phase.

        Args:
            chunks: List of Chunk objects
            output_dir: Base output directory
            chapters_config: Optional list of chapter configurations

        Returns:
            FileOrganizationMetadata instance
        """
        logger.info("Starting file organization phase")
        metadata = self.organizer.run(chunks, output_dir, chapters_config)
        logger.info("File organization phase complete")
        return metadata

    def save_organization_report(
        self, metadata: FileOrganizationMetadata, output_path: str
    ) -> None:
        """
        Save file organization report to JSON.

        Args:
            metadata: FileOrganizationMetadata instance
            output_path: Path to save the report
        """
        report = {
            "total_chunks_saved": metadata.total_chunks_saved,
            "total_chapters": metadata.total_chapters,
            "total_parts": metadata.total_parts,
            "index_file_path": metadata.index_file_path,
            "chunks_by_chapter": metadata.chunks_by_chapter,
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"Organization report saved to: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save organization report: {e}")
