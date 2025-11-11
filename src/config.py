"""
Configuration management for the PDF RAG parser.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


logger = logging.getLogger(__name__)


@dataclass
class ExtractionConfig:
    """Configuration for the extraction phase."""

    library: str = "pymupdf"  # "pymupdf" or "pdfplumber"
    extract_metadata: bool = True


@dataclass
class StructureConfig:
    """Configuration for structure analysis phase."""

    use_bookmarks: bool = True
    use_heuristics: bool = True
    use_regex: bool = True
    font_size_threshold: float = 14.0
    heading_isolation_threshold: float = 0.7

    # Regex patterns for structure detection
    part_pattern: str = r"^(?:Part|PART)\s+([IVX]+|[0-9]+)[\s:]*(.*)$"
    chapter_pattern: str = r"^(?:Chapter|CHAPTER)\s+([0-9]+)[\s:]*(.*)$"
    section_pattern: str = r"^([0-9]+\.[0-9]+)\s+(.*)$"
    subsection_pattern: str = r"^([0-9]+\.[0-9]+\.[0-9]+)\s+(.*)$"


@dataclass
class CleaningConfig:
    """Configuration for the cleaning phase."""

    exclude_sections: list = None
    exclude_patterns: list = None
    exclude_pages: list = None
    crop_top_percent: float = 0.0
    crop_bottom_percent: float = 5.0
    crop_left_percent: float = 0.0
    crop_right_percent: float = 0.0

    def __post_init__(self):
        """Initialize default values for list fields."""
        if self.exclude_sections is None:
            self.exclude_sections = ["Index", "Bibliography", "Appendix", "References"]
        if self.exclude_patterns is None:
            self.exclude_patterns = [r"[Pp]age \d+", r"^\s*$", r"^\s*-{3,}\s*$"]
        if self.exclude_pages is None:
            self.exclude_pages = []


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
    """Main configuration for the entire pipeline."""

    extraction: ExtractionConfig = None
    structure: StructureConfig = None
    cleaning: CleaningConfig = None
    chunking: ChunkingConfig = None
    output: OutputConfig = None

    def __post_init__(self):
        """Initialize default configurations."""
        if self.extraction is None:
            self.extraction = ExtractionConfig()
        if self.structure is None:
            self.structure = StructureConfig()
        if self.cleaning is None:
            self.cleaning = CleaningConfig()
        if self.chunking is None:
            self.chunking = ChunkingConfig()
        if self.output is None:
            self.output = OutputConfig()


class ConfigManager:
    """Manages configuration loading and validation."""

    @staticmethod
    def load_config(config_path: Optional[str] = None) -> PipelineConfig:
        """
        Load configuration from a JSON file or use defaults.

        Args:
            config_path: Path to configuration JSON file (optional)

        Returns:
            PipelineConfig instance
        """
        if config_path is None:
            logger.info("Using default configuration")
            return PipelineConfig()

        config_file = Path(config_path)

        if not config_file.exists():
            logger.warning(f"Config file not found: {config_path}. Using defaults.")
            return PipelineConfig()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_dict = json.load(f)

            logger.info(f"Loaded configuration from: {config_path}")
            return ConfigManager._dict_to_config(config_dict)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise

    @staticmethod
    def _dict_to_config(config_dict: Dict[str, Any]) -> PipelineConfig:
        """
        Convert dictionary to PipelineConfig object.

        Args:
            config_dict: Configuration dictionary

        Returns:
            PipelineConfig instance
        """
        extraction_dict = config_dict.get("extraction", {})
        structure_dict = config_dict.get("structure", {})
        cleaning_dict = config_dict.get("cleaning", {})
        chunking_dict = config_dict.get("chunking", {})
        output_dict = config_dict.get("output", {})

        return PipelineConfig(
            extraction=ExtractionConfig(**extraction_dict),
            structure=StructureConfig(**structure_dict),
            cleaning=CleaningConfig(**cleaning_dict),
            chunking=ChunkingConfig(**chunking_dict),
            output=OutputConfig(**output_dict),
        )

    @staticmethod
    def save_config(config: PipelineConfig, output_path: str) -> None:
        """
        Save configuration to a JSON file.

        Args:
            config: PipelineConfig instance
            output_path: Path to save configuration
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        config_dict = {
            "extraction": asdict(config.extraction),
            "structure": asdict(config.structure),
            "cleaning": asdict(config.cleaning),
            "chunking": asdict(config.chunking),
            "output": asdict(config.output),
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"Configuration saved to: {output_path}")

    @staticmethod
    def get_default_config_json() -> str:
        """
        Get default configuration as JSON string.

        Returns:
            JSON string of default configuration
        """
        config = PipelineConfig()
        config_dict = {
            "extraction": asdict(config.extraction),
            "structure": asdict(config.structure),
            "cleaning": asdict(config.cleaning),
            "chunking": asdict(config.chunking),
            "output": asdict(config.output),
        }

        return json.dumps(config_dict, indent=2)
