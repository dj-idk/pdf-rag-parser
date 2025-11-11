"""
Phase 5: File Organization & Output

Organizes chunks into a structured folder hierarchy with metadata tracking.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


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
        """Initialize default values."""
        if self.folder_structure is None:
            self.folder_structure = {}
        if self.chunks_by_chapter is None:
            self.chunks_by_chapter = {}


class FileOrganizationPhase:
    """Handles file organization and output generation."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize file organization phase.

        Args:
            config: Configuration dictionary for output phase
        """
        self.config = config
        self.create_metadata = config.get("create_metadata", True)
        self.create_index = config.get("create_index", True)
        self.preserve_structure = config.get("preserve_structure", True)

    def run(
        self,
        chunks: List[Dict[str, Any]],
        output_dir: str,
        structure_metadata: Optional[Dict[str, Any]] = None,
    ) -> FileOrganizationMetadata:
        """
        Organize chunks into folder structure and create metadata.

        Args:
            chunks: List of chunk dictionaries
            output_dir: Base output directory
            structure_metadata: Metadata from structure analysis phase

        Returns:
            FileOrganizationMetadata instance
        """
        logger.info(f"Organizing {len(chunks)} chunks into folder structure...")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Build folder structure
        folder_structure = self._build_folder_structure(chunks, structure_metadata)

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
                chunks, output_path, folder_structure, structure_metadata
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
        chunks: List[Dict[str, Any]],
        structure_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build hierarchical folder structure from chunks.

        Args:
            chunks: List of chunk dictionaries
            structure_metadata: Metadata from structure analysis

        Returns:
            Dictionary representing folder structure
        """
        structure = {}

        for chunk in chunks:
            part = chunk.get("part", "Uncategorized")
            chapter = chunk.get("chapter", "Uncategorized")

            if part not in structure:
                structure[part] = {"chapters": {}}

            if chapter not in structure[part]["chapters"]:
                structure[part]["chapters"][chapter] = {
                    "chunks": [],
                    "pages": set(),
                    "total_characters": 0,
                }

            structure[part]["chapters"][chapter]["chunks"].append(chunk)
            structure[part]["chapters"][chapter]["total_characters"] += len(
                chunk.get("content", "")
            )

            # Track pages
            if "page_num" in chunk:
                structure[part]["chapters"][chapter]["pages"].add(chunk["page_num"])

        return structure

    def _save_chunks_to_folders(
        self,
        chunks: List[Dict[str, Any]],
        output_path: Path,
        folder_structure: Dict[str, Any],
    ) -> int:
        """
        Save chunks to organized folder structure.

        Args:
            chunks: List of chunk dictionaries
            output_path: Base output directory path
            folder_structure: Folder structure dictionary

        Returns:
            Total number of chunks saved
        """
        total_saved = 0

        for part_name, part_data in folder_structure.items():
            part_folder = self._sanitize_folder_name(part_name)
            part_path = output_path / part_folder

            for chapter_name, chapter_data in part_data["chapters"].items():
                chapter_folder = self._sanitize_folder_name(chapter_name)
                chapter_path = part_path / chapter_folder
                chapter_path.mkdir(parents=True, exist_ok=True)

                # Save chunks for this chapter
                for idx, chunk in enumerate(chapter_data["chunks"], 1):
                    chunk_filename = f"chunk_{idx:03d}.txt"
                    chunk_file_path = chapter_path / chunk_filename

                    with open(chunk_file_path, "w", encoding="utf-8") as f:
                        f.write(chunk.get("content", ""))

                    total_saved += 1

        return total_saved

    def _create_chapter_metadata(
        self,
        chunks: List[Dict[str, Any]],
        output_path: Path,
        folder_structure: Dict[str, Any],
    ) -> None:
        """
        Create metadata.json file for each chapter.

        Args:
            chunks: List of chunk dictionaries
            output_path: Base output directory path
            folder_structure: Folder structure dictionary
        """
        for part_name, part_data in folder_structure.items():
            part_folder = self._sanitize_folder_name(part_name)
            part_path = output_path / part_folder

            for chapter_name, chapter_data in part_data["chapters"].items():
                chapter_folder = self._sanitize_folder_name(chapter_name)
                chapter_path = part_path / chapter_folder

                # Create metadata
                metadata = {
                    "chapter": chapter_name,
                    "part": part_name,
                    "total_chunks": len(chapter_data["chunks"]),
                    "total_characters": chapter_data["total_characters"],
                    "source_pages": sorted(list(chapter_data["pages"])),
                }

                # Save metadata
                metadata_file = chapter_path / "metadata.json"
                with open(metadata_file, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

                logger.debug(
                    f"Created metadata for {chapter_name}: {len(chapter_data['chunks'])} chunks"
                )

    def _create_index_file(
        self,
        chunks: List[Dict[str, Any]],
        output_path: Path,
        folder_structure: Dict[str, Any],
        structure_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create index.json file mapping entire document structure.

        Args:
            chunks: List of chunk dictionaries
            output_path: Base output directory path
            folder_structure: Folder structure dictionary
            structure_metadata: Metadata from structure analysis

        Returns:
            Path to index file
        """
        # Calculate totals
        total_chunks = sum(
            len(chapter_data["chunks"])
            for part_data in folder_structure.values()
            for chapter_data in part_data["chapters"].values()
        )

        total_characters = sum(
            chapter_data["total_characters"]
            for part_data in folder_structure.values()
            for chapter_data in part_data["chapters"].values()
        )

        # Build structure array
        structure_array = []
        for part_name, part_data in folder_structure.items():
            part_entry = {"part": part_name, "chapters": []}

            for chapter_name, chapter_data in part_data["chapters"].items():
                chapter_folder = self._sanitize_folder_name(chapter_name)
                part_folder = self._sanitize_folder_name(part_name)
                chapter_path = f"{part_folder}/{chapter_folder}"

                chapter_entry = {
                    "name": chapter_name,
                    "chunks": len(chapter_data["chunks"]),
                    "characters": chapter_data["total_characters"],
                    "pages": sorted(list(chapter_data["pages"])),
                    "path": chapter_path,
                }

                part_entry["chapters"].append(chapter_entry)

            structure_array.append(part_entry)

        # Create index
        index = {
            "source_pdf": (
                structure_metadata.get("source_pdf", "unknown.pdf")
                if structure_metadata
                else "unknown.pdf"
            ),
            "total_chunks": total_chunks,
            "total_characters": total_characters,
            "total_parts": len(folder_structure),
            "total_chapters": len(self._get_all_chapters(folder_structure)),
            "structure": structure_array,
        }

        # Save index
        index_file = output_path / "index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

        logger.info(f"Created index file: {index_file}")
        return str(index_file)

    def _sanitize_folder_name(self, name: str) -> str:
        """
        Convert chapter/part name to safe folder name.

        Args:
            name: Original chapter/part name

        Returns:
            Sanitized folder name
        """
        # Remove special characters, keep alphanumeric, spaces, and hyphens
        sanitized = re.sub(r"[^\w\s\-]", "", name)

        # Replace spaces with underscores
        sanitized = re.sub(r"\s+", "_", sanitized)

        # Remove leading/trailing underscores
        sanitized = sanitized.strip("_")

        # Limit length to 100 characters
        sanitized = sanitized[:100]

        return sanitized if sanitized else "Uncategorized"

    def _get_all_chapters(self, folder_structure: Dict[str, Any]) -> List[str]:
        """
        Get list of all chapters from folder structure.

        Args:
            folder_structure: Folder structure dictionary

        Returns:
            List of chapter names
        """
        chapters = []
        for part_data in folder_structure.values():
            chapters.extend(part_data["chapters"].keys())
        return chapters

    def _count_chunks_by_chapter(
        self, chunks: List[Dict[str, Any]], folder_structure: Dict[str, Any]
    ) -> Dict[str, int]:
        """
        Count chunks by chapter.

        Args:
            chunks: List of chunk dictionaries
            folder_structure: Folder structure dictionary

        Returns:
            Dictionary mapping chapter names to chunk counts
        """
        counts = {}
        for part_data in folder_structure.values():
            for chapter_name, chapter_data in part_data["chapters"].items():
                counts[chapter_name] = len(chapter_data["chunks"])
        return counts

    def save_file_organization_report(
        self, metadata: FileOrganizationMetadata, output_path: str
    ) -> None:
        """
        Save file organization report to JSON file.

        Args:
            metadata: FileOrganizationMetadata instance
            output_path: Path to save report
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

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"File organization report saved to: {output_path}")
