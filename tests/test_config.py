"""
Tests for configuration management.
"""

import pytest
import json
import tempfile
from pathlib import Path

from src.config import (
    ExtractionConfig,
    StructureConfig,
    CleaningConfig,
    ChunkingConfig,
    OutputConfig,
    PipelineConfig,
    ConfigManager,
)


class TestExtractionConfig:
    """Test ExtractionConfig dataclass."""

    def test_default_extraction_config(self):
        """Test default extraction configuration."""
        config = ExtractionConfig()
        assert config.library == "pymupdf"
        assert config.extract_metadata is True

    def test_custom_extraction_config(self):
        """Test custom extraction configuration."""
        config = ExtractionConfig(library="pdfplumber", extract_metadata=False)
        assert config.library == "pdfplumber"
        assert config.extract_metadata is False


class TestStructureConfig:
    """Test StructureConfig dataclass."""

    def test_default_structure_config(self):
        """Test default structure configuration."""
        config = StructureConfig()
        assert config.use_bookmarks is True
        assert config.use_heuristics is True
        assert config.use_regex is True
        assert config.font_size_threshold == 14.0


class TestCleaningConfig:
    """Test CleaningConfig dataclass."""

    def test_default_cleaning_config(self):
        """Test default cleaning configuration."""
        config = CleaningConfig()
        assert len(config.exclude_sections) > 0
        assert len(config.exclude_patterns) > 0
        assert config.crop_bottom_percent == 5.0

    def test_custom_cleaning_config(self):
        """Test custom cleaning configuration."""
        config = CleaningConfig(
            exclude_sections=["Index"],
            exclude_patterns=[r"\d+"],
            crop_bottom_percent=10.0,
        )
        assert config.exclude_sections == ["Index"]
        assert config.crop_bottom_percent == 10.0


class TestChunkingConfig:
    """Test ChunkingConfig dataclass."""

    def test_default_chunking_config(self):
        """Test default chunking configuration."""
        config = ChunkingConfig()
        assert config.max_chunk_size == 800
        assert config.chunk_overlap == 0
        assert config.split_by_paragraph is True


class TestOutputConfig:
    """Test OutputConfig dataclass."""

    def test_default_output_config(self):
        """Test default output configuration."""
        config = OutputConfig()
        assert config.output_dir == "output/"
        assert config.create_metadata is True
        assert config.create_index is True


class TestPipelineConfig:
    """Test PipelineConfig dataclass."""

    def test_default_pipeline_config(self):
        """Test default pipeline configuration."""
        config = PipelineConfig()
        assert isinstance(config.extraction, ExtractionConfig)
        assert isinstance(config.structure, StructureConfig)
        assert isinstance(config.cleaning, CleaningConfig)
        assert isinstance(config.chunking, ChunkingConfig)
        assert isinstance(config.output, OutputConfig)

    def test_custom_pipeline_config(self):
        """Test custom pipeline configuration."""
        extraction = ExtractionConfig(library="pdfplumber")
        output = OutputConfig(output_dir="custom_output/")

        config = PipelineConfig(extraction=extraction, output=output)
        assert config.extraction.library == "pdfplumber"
        assert config.output.output_dir == "custom_output/"


class TestConfigManager:
    """Test ConfigManager class."""

    def test_load_default_config(self):
        """Test loading default configuration."""
        config = ConfigManager.load_config()
        assert isinstance(config, PipelineConfig)
        assert config.extraction.library == "pymupdf"

    def test_load_config_from_file(self):
        """Test loading configuration from JSON file."""
        config_dict = {
            "extraction": {"library": "pdfplumber"},
            "output": {"output_dir": "custom_output/"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_dict, f)
            temp_path = f.name

        try:
            config = ConfigManager.load_config(temp_path)
            assert config.extraction.library == "pdfplumber"
            assert config.output.output_dir == "custom_output/"
        finally:
            Path(temp_path).unlink()

    def test_load_config_missing_file(self):
        """Test loading configuration from non-existent file."""
        config = ConfigManager.load_config("/nonexistent/config.json")
        assert isinstance(config, PipelineConfig)

    def test_load_config_invalid_json(self):
        """Test loading configuration from invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            with pytest.raises(json.JSONDecodeError):
                ConfigManager.load_config(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_save_config(self):
        """Test saving configuration to file."""
        config = PipelineConfig()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            ConfigManager.save_config(config, str(config_path))

            assert config_path.exists()

            with open(config_path, "r") as f:
                saved_dict = json.load(f)

            assert "extraction" in saved_dict
            assert "structure" in saved_dict
            assert "cleaning" in saved_dict
            assert "chunking" in saved_dict
            assert "output" in saved_dict

    def test_dict_to_config(self):
        """Test converting dictionary to PipelineConfig."""
        config_dict = {
            "extraction": {"library": "pdfplumber"},
            "chunking": {"max_chunk_size": 1000},
        }

        config = ConfigManager._dict_to_config(config_dict)
        assert config.extraction.library == "pdfplumber"
        assert config.chunking.max_chunk_size == 1000

    def test_get_default_config_json(self):
        """Test getting default configuration as JSON."""
        json_str = ConfigManager.get_default_config_json()
        config_dict = json.loads(json_str)

        assert "extraction" in config_dict
        assert "structure" in config_dict
        assert "cleaning" in config_dict
        assert "chunking" in config_dict
        assert "output" in config_dict

    def test_save_and_load_config_roundtrip(self):
        """Test saving and loading configuration maintains data."""
        original_config = PipelineConfig(
            extraction=ExtractionConfig(library="pdfplumber"),
            output=OutputConfig(output_dir="test_output/"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            ConfigManager.save_config(original_config, str(config_path))
            loaded_config = ConfigManager.load_config(str(config_path))

            assert loaded_config.extraction.library == "pdfplumber"
            assert loaded_config.output.output_dir == "test_output/"
