"""Tests for EntityExtractor and Pydantic extraction models.

The Gemini API is not called in these tests. We test static/utility
methods, Pydantic model validation, and availability checks.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from src.processors.entity_extractor import (
    EntityExtractor,
    ExtractionResult,
    ExtractedEntity,
    ExtractedRelation,
)


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------


class TestExtractionModels:
    """Tests for Pydantic data models."""

    def test_extracted_entity_creation(self):
        entity = ExtractedEntity(
            name="Python", type="Technology", description="Programming language"
        )
        assert entity.name == "Python"
        assert entity.type == "Technology"
        assert entity.description == "Programming language"

    def test_extracted_relation_creation(self):
        relation = ExtractedRelation(
            source="Python", target="Web", relation="used_for"
        )
        assert relation.source == "Python"
        assert relation.target == "Web"

    def test_extraction_result_creation(self):
        result = ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Python", type="Technology", description="A language"
                ),
                ExtractedEntity(
                    name="Django", type="Technology", description="A framework"
                ),
            ],
            relations=[
                ExtractedRelation(
                    source="Django", target="Python", relation="built_with"
                )
            ],
        )
        assert len(result.entities) == 2
        assert len(result.relations) == 1

    def test_extraction_result_empty(self):
        result = ExtractionResult(entities=[], relations=[])
        assert result.entities == []
        assert result.relations == []

    def test_entity_requires_all_fields(self):
        with pytest.raises(Exception):
            ExtractedEntity(name="Python")  # Missing type and description

    def test_relation_requires_all_fields(self):
        with pytest.raises(Exception):
            ExtractedRelation(source="A")  # Missing target and relation


# ---------------------------------------------------------------------------
# EntityExtractor._normalize_name
# ---------------------------------------------------------------------------


class TestNormalizeName:
    """Tests for entity name normalization."""

    def test_strips_whitespace(self):
        assert EntityExtractor._normalize_name("  Hello World  ") == "hello world"

    def test_lowercases(self):
        assert EntityExtractor._normalize_name("UPPER") == "upper"

    def test_japanese_unchanged(self):
        assert EntityExtractor._normalize_name("日本語テスト") == "日本語テスト"

    def test_mixed_content(self):
        assert EntityExtractor._normalize_name("  Python 3.12  ") == "python 3.12"

    def test_empty_string(self):
        assert EntityExtractor._normalize_name("") == ""


# ---------------------------------------------------------------------------
# EntityExtractor.is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    """Tests for API key availability check."""

    def test_available_with_config_key(self):
        config = MagicMock()
        config.get.return_value = "fake-api-key-12345"
        assert EntityExtractor.is_available(config) is True

    def test_unavailable_with_empty_config_and_no_env(self):
        config = MagicMock()
        config.get.return_value = ""
        with patch.dict(os.environ, {}, clear=False):
            # Temporarily remove GEMINI_API_KEY if present
            env_backup = os.environ.pop("GEMINI_API_KEY", None)
            try:
                assert EntityExtractor.is_available(config) is False
            finally:
                if env_backup is not None:
                    os.environ["GEMINI_API_KEY"] = env_backup

    def test_available_via_env_variable(self):
        config = MagicMock()
        # config.get returns the env var value via its default arg
        config.get.side_effect = lambda key, default=None: default
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-key-value"}):
            # The implementation does: config.get("gemini.api_key", os.getenv("GEMINI_API_KEY", ""))
            # Since config.get returns its default, it will use os.getenv result
            config.get.return_value = os.getenv("GEMINI_API_KEY", "")
            assert EntityExtractor.is_available(config) is True


# ---------------------------------------------------------------------------
# EntityExtractor.__init__ validation
# ---------------------------------------------------------------------------


class TestEntityExtractorInit:
    """Tests for constructor validation."""

    def test_raises_without_api_key(self):
        config = MagicMock()
        config.get.return_value = ""
        with patch.dict(os.environ, {}, clear=False):
            env_backup = os.environ.pop("GEMINI_API_KEY", None)
            try:
                with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                    EntityExtractor(config)
            finally:
                if env_backup is not None:
                    os.environ["GEMINI_API_KEY"] = env_backup

    @patch("src.processors.entity_extractor.genai.Client")
    def test_creates_with_valid_key(self, mock_client_cls):
        config = MagicMock()
        config.get.return_value = "valid-key"
        extractor = EntityExtractor(config)
        assert extractor.model == "gemini-2.5-flash"
        assert extractor.max_retries == 3
        mock_client_cls.assert_called_once_with(api_key="valid-key")


# ---------------------------------------------------------------------------
# EntityExtractor.extract_from_chunk edge cases
# ---------------------------------------------------------------------------


class TestExtractFromChunkEdgeCases:
    """Tests for edge cases in single-chunk extraction."""

    @patch("src.processors.entity_extractor.genai.Client")
    def test_empty_text_returns_none(self, mock_client_cls):
        config = MagicMock()
        config.get.return_value = "key"
        extractor = EntityExtractor(config)
        assert extractor.extract_from_chunk("") is None

    @patch("src.processors.entity_extractor.genai.Client")
    def test_whitespace_only_returns_none(self, mock_client_cls):
        config = MagicMock()
        config.get.return_value = "key"
        extractor = EntityExtractor(config)
        assert extractor.extract_from_chunk("   \n  ") is None
