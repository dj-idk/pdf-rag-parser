from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
import json


@dataclass
class ChapterConfig:
    """Configuration for a single chapter."""

    name: str
    part: str
    start_page: int
    end_page: int
    lessons: List[str] = field(default_factory=list)


@dataclass
class ExtractionConfig:
    """Configuration for the extraction phase."""

    library: str = "pymupdf"
    extract_metadata: bool = True


@dataclass
class CleaningConfig:
    """Configuration for the cleaning phase."""

    exclude_sections: List[str] = field(
        default_factory=lambda: ["به کارببندیم", "فعّالیت", "بیشتر بدانیم"]
    )
    exclude_patterns: List[str] = field(
        default_factory=lambda: [r"[Pp]age \d+", r"^\s*$", r"^\s*-{3,}\s*$"]
    )
    exclude_exact_blocks: List[str] = field(
        default_factory=lambda: ["به کاربندیم", "فعّالیت", "بیشتر بدانیم"]
    )
    exclude_pages: List[int] = field(default_factory=list)
    crop_top_percent: float = 0.0
    crop_bottom_percent: float = 5.0
    crop_left_percent: float = 0.0
    crop_right_percent: float = 0.0


@dataclass
class ChunkingConfig:
    """Configuration for the chunking phase."""

    max_chunk_size: int = 800
    chunk_overlap: int = 0
    split_by_paragraph: bool = True
    split_by_sentence: bool = True
    split_by_word: bool = True


@dataclass
class OutputConfig:
    """Configuration for the output phase."""

    output_dir: str = "output/"
    create_metadata: bool = True
    create_index: bool = True
    preserve_structure: bool = True


@dataclass
class PipelineConfig:
    """Main pipeline configuration."""

    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    cleaning: CleaningConfig = field(default_factory=CleaningConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    chapters: List[ChapterConfig] = field(default_factory=list)

    @classmethod
    def from_json(cls, config_path: str) -> "PipelineConfig":
        """Load configuration from JSON file."""
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Parse chapters
        chapters = []
        for chapter_data in data.get("chapters", []):
            chapters.append(ChapterConfig(**chapter_data))

        # Parse configs
        extraction = ExtractionConfig(**data.get("extraction", {}))
        cleaning = CleaningConfig(**data.get("cleaning", {}))
        chunking = ChunkingConfig(**data.get("chunking", {}))
        output = OutputConfig(**data.get("output", {}))

        return cls(
            extraction=extraction,
            cleaning=cleaning,
            chunking=chunking,
            output=output,
            chapters=chapters,
        )

    def to_json(self, output_path: str) -> None:
        """Save configuration to JSON file."""
        data = {
            "extraction": self.extraction.__dict__,
            "cleaning": self.cleaning.__dict__,
            "chunking": self.chunking.__dict__,
            "output": self.output.__dict__,
            "chapters": [c.__dict__ for c in self.chapters],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
