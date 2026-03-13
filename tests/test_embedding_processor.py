"""Tests for EmbeddingProcessor and related helpers.

Heavy dependencies (torch, transformers) are mocked so tests run fast
without downloading models.
"""

from unittest.mock import MagicMock

import pytest

from tests.conftest import MockConfig

# ---------------------------------------------------------------------------
# _is_e5_model (module-level helper)
# ---------------------------------------------------------------------------


class TestIsE5Model:
    """Tests for E5 model name detection."""

    def test_multilingual_e5(self):
        from src.processors.embedding_processor import _is_e5_model

        assert _is_e5_model("intfloat/multilingual-e5-base") is True

    def test_e5_large(self):
        from src.processors.embedding_processor import _is_e5_model

        assert _is_e5_model("intfloat/e5-large") is True

    def test_non_e5_model(self):
        from src.processors.embedding_processor import _is_e5_model

        assert _is_e5_model("sentence-transformers/all-MiniLM-L6-v2") is False

    def test_case_insensitive(self):
        from src.processors.embedding_processor import _is_e5_model

        assert _is_e5_model("intfloat/E5-base") is True

    def test_empty_string(self):
        from src.processors.embedding_processor import _is_e5_model

        assert _is_e5_model("") is False


# ---------------------------------------------------------------------------
# EmbeddingProcessor._add_prefix
# ---------------------------------------------------------------------------


class TestAddPrefix:
    """Tests for E5 prefix behavior."""

    def test_e5_query_prefix(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        assert proc._add_prefix("hello", "query") == "query: hello"

    def test_e5_passage_prefix(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        assert proc._add_prefix("hello", "passage") == "passage: hello"

    def test_non_e5_no_prefix(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        config = MockConfig(
            {"embedding.model_name": "sentence-transformers/all-MiniLM-L6-v2"}
        )
        proc = EmbeddingProcessor(config)
        assert proc._add_prefix("hello", "query") == "hello"
        assert proc._add_prefix("hello", "passage") == "hello"


# ---------------------------------------------------------------------------
# EmbeddingProcessor.get_embedding (empty text edge case)
# ---------------------------------------------------------------------------


class TestGetEmbedding:
    """Tests for embedding generation with mocked model."""

    def test_empty_text_returns_zero_vector(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        # Manually set model/tokenizer so load_model is not called
        proc.model = MagicMock()
        proc.tokenizer = MagicMock()
        result = proc.get_embedding("")
        assert result == [0.0] * 768

    def test_none_text_returns_zero_vector(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        proc.model = MagicMock()
        proc.tokenizer = MagicMock()
        result = proc.get_embedding(None)
        assert result == [0.0] * 768

    def test_get_query_embedding_delegates(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        proc.get_embedding = MagicMock(return_value=[0.1] * 768)
        proc.get_query_embedding("test")
        proc.get_embedding.assert_called_once_with("test", prefix_type="query")

    def test_get_passage_embedding_delegates(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        proc.get_embedding = MagicMock(return_value=[0.1] * 768)
        proc.get_passage_embedding("test")
        proc.get_embedding.assert_called_once_with("test", prefix_type="passage")


# ---------------------------------------------------------------------------
# EmbeddingProcessor.vector_similarity
# ---------------------------------------------------------------------------


class TestVectorSimilarity:
    """Tests for cosine similarity calculation."""

    def test_identical_vectors(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        vec = [1.0, 0.0, 0.0]
        assert proc.vector_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        assert proc.vector_similarity(vec1, vec2) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        assert proc.vector_similarity(vec1, vec2) == pytest.approx(-1.0)

    def test_dimension_mismatch_raises(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        with pytest.raises(ValueError, match="dimensions do not match"):
            proc.vector_similarity([1.0, 0.0], [1.0, 0.0, 0.0])

    def test_zero_vector_returns_zero(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        assert proc.vector_similarity([0.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)

    def test_high_dimensional_similarity(self):
        """Verify similarity works with realistic 768-dim vectors."""
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        vec = [1.0 / 768] * 768
        assert proc.vector_similarity(vec, vec) == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# EmbeddingProcessor.unload_model
# ---------------------------------------------------------------------------


class TestUnloadModel:
    """Tests for model cleanup."""

    def test_unload_clears_model(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        proc.model = MagicMock()
        proc.tokenizer = MagicMock()
        proc.unload_model()
        assert proc.model is None
        assert proc.tokenizer is None

    def test_unload_when_already_none(self):
        from src.processors.embedding_processor import EmbeddingProcessor

        proc = EmbeddingProcessor(MockConfig())
        # Should not raise
        proc.unload_model()
        assert proc.model is None
