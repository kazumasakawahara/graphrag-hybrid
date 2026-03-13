"""Tests for QueryEngine with mocked database managers.

All external dependencies (Neo4j, Qdrant, embedding model) are replaced
with MagicMock objects so tests run without infrastructure.
"""

from unittest.mock import MagicMock

import pytest

from src.query_engine import QueryEngine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_neo4j():
    manager = MagicMock()
    manager.driver = True  # Passes _verify_connections check
    manager.get_document_by_id.return_value = {
        "id": "doc1",
        "title": "Test",
        "category": "test",
    }
    manager.get_chunk_context.return_value = {"previous": [], "next": []}
    manager.get_related_documents.return_value = []
    manager.search_by_entity.return_value = []
    manager.get_document_chunks.return_value = [
        {"id": "chunk1", "text": "text", "position": 0}
    ]
    manager.get_all_categories.return_value = ["test", "docs"]
    manager.get_statistics.return_value = {"document_count": 5, "chunk_count": 20}
    manager.get_document_by_chunk_id.return_value = "doc1"
    manager.get_entity_graph.return_value = {
        "entity": "Python",
        "relations": [],
    }
    return manager


@pytest.fixture
def mock_qdrant():
    manager = MagicMock()
    manager.client = True  # Passes _verify_connections check
    manager.search.return_value = [
        {
            "id": "chunk1",
            "score": 0.9,
            "text": "test text",
            "doc_id": "doc1",
            "position": 0,
        }
    ]
    manager.get_statistics.return_value = {"vector_count": 20}
    return manager


@pytest.fixture
def mock_embedding():
    proc = MagicMock()
    proc.get_query_embedding.return_value = [0.1] * 768
    return proc


@pytest.fixture
def engine(mock_neo4j, mock_qdrant, mock_embedding):
    return QueryEngine(mock_neo4j, mock_qdrant, mock_embedding)


# ---------------------------------------------------------------------------
# Construction & connection verification
# ---------------------------------------------------------------------------


class TestQueryEngineInit:
    """Tests for initialization and connection verification."""

    def test_creates_with_valid_connections(self, mock_neo4j, mock_qdrant, mock_embedding):
        engine = QueryEngine(mock_neo4j, mock_qdrant, mock_embedding)
        assert engine.neo4j is mock_neo4j
        assert engine.qdrant is mock_qdrant

    def test_reconnects_when_neo4j_driver_missing(self, mock_qdrant, mock_embedding):
        neo4j = MagicMock()
        neo4j.driver = None  # Trigger reconnect
        QueryEngine(neo4j, mock_qdrant, mock_embedding)
        neo4j.connect.assert_called_once()

    def test_reconnects_when_qdrant_client_missing(self, mock_neo4j, mock_embedding):
        qdrant = MagicMock()
        qdrant.client = None  # Trigger reconnect
        QueryEngine(mock_neo4j, qdrant, mock_embedding)
        qdrant.connect.assert_called_once()


# ---------------------------------------------------------------------------
# semantic_search
# ---------------------------------------------------------------------------


class TestSemanticSearch:
    """Tests for vector-based semantic search."""

    def test_returns_results(self, engine, mock_qdrant):
        results = engine.semantic_search("test query", limit=5)
        assert len(results) >= 1
        mock_qdrant.search.assert_called_once()

    def test_passes_category_filter(self, engine, mock_qdrant):
        engine.semantic_search("test", category="docs")
        call_kwargs = mock_qdrant.search.call_args
        assert call_kwargs[1]["filter_conditions"] == {"category": "docs"}

    def test_no_category_passes_none(self, engine, mock_qdrant):
        engine.semantic_search("test")
        call_kwargs = mock_qdrant.search.call_args
        assert call_kwargs[1]["filter_conditions"] is None

    def test_returns_empty_without_embedding_processor(self, mock_neo4j, mock_qdrant):
        engine = QueryEngine(mock_neo4j, mock_qdrant, embedding_processor=None)
        results = engine.semantic_search("test")
        assert results == []

    def test_enriches_with_document_info(self, engine, mock_neo4j):
        results = engine.semantic_search("test")
        assert results[0].get("document") is not None
        mock_neo4j.get_document_by_id.assert_called()

    def test_handles_search_exception(self, engine, mock_qdrant):
        mock_qdrant.search.side_effect = Exception("connection lost")
        results = engine.semantic_search("test")
        assert results == []


# ---------------------------------------------------------------------------
# category_search
# ---------------------------------------------------------------------------


class TestCategorySearch:
    """Tests for Neo4j category-based search."""

    def test_returns_results(self, engine, mock_neo4j):
        mock_neo4j.search_by_category.return_value = [
            {"id": "doc1", "title": "Test"}
        ]
        results = engine.category_search("test")
        assert len(results) == 1

    def test_handles_exception(self, engine, mock_neo4j):
        mock_neo4j.search_by_category.side_effect = Exception("db error")
        results = engine.category_search("test")
        assert results == []


# ---------------------------------------------------------------------------
# hybrid_search
# ---------------------------------------------------------------------------


class TestHybridSearch:
    """Tests for combined semantic + graph + entity search."""

    def test_returns_list(self, engine):
        results = engine.hybrid_search("test query", limit=5)
        assert isinstance(results, list)

    def test_respects_limit(self, engine, mock_qdrant):
        # Return many semantic results
        mock_qdrant.search.return_value = [
            {"id": f"c{i}", "score": 0.9 - i * 0.1, "text": f"t{i}", "doc_id": "d1", "position": i}
            for i in range(10)
        ]
        results = engine.hybrid_search("test", limit=3)
        assert len(results) <= 3

    def test_calculates_final_score(self, engine, mock_qdrant):
        results = engine.hybrid_search("test", limit=5)
        if results:
            assert "final_score" in results[0]
            assert results[0]["final_score"] > 0

    def test_returns_empty_when_no_semantic_results(self, engine, mock_qdrant):
        mock_qdrant.search.return_value = []
        results = engine.hybrid_search("test")
        assert results == []

    def test_handles_exception(self, engine, mock_qdrant):
        mock_qdrant.search.side_effect = Exception("timeout")
        results = engine.hybrid_search("test")
        assert results == []

    def test_custom_weights(self, engine):
        results = engine.hybrid_search(
            "test",
            semantic_weight=0.8,
            graph_weight=0.1,
            entity_weight=0.1,
        )
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# entity_search
# ---------------------------------------------------------------------------


class TestEntitySearch:
    """Tests for entity-based search."""

    def test_delegates_to_neo4j(self, engine, mock_neo4j):
        mock_neo4j.search_by_entity.return_value = [
            {"entity_name": "Python", "mentions": []}
        ]
        results = engine.entity_search("Python")
        assert len(results) == 1
        mock_neo4j.search_by_entity.assert_called_with("Python", 10)

    def test_handles_exception(self, engine, mock_neo4j):
        mock_neo4j.search_by_entity.side_effect = Exception("error")
        results = engine.entity_search("Python")
        assert results == []


# ---------------------------------------------------------------------------
# get_entity_graph
# ---------------------------------------------------------------------------


class TestGetEntityGraph:
    """Tests for entity graph retrieval."""

    def test_returns_graph(self, engine, mock_neo4j):
        result = engine.get_entity_graph("Python")
        assert result.get("entity") == "Python"

    def test_returns_empty_on_none(self, engine, mock_neo4j):
        mock_neo4j.get_entity_graph.return_value = None
        result = engine.get_entity_graph("unknown")
        assert result == {}

    def test_handles_exception(self, engine, mock_neo4j):
        mock_neo4j.get_entity_graph.side_effect = Exception("error")
        result = engine.get_entity_graph("Python")
        assert result == {}


# ---------------------------------------------------------------------------
# expand_context
# ---------------------------------------------------------------------------


class TestExpandContext:
    """Tests for chunk context expansion."""

    def test_returns_context(self, engine, mock_neo4j):
        mock_neo4j.get_chunk_context.return_value = {
            "center": {"id": "chunk1", "text": "center text"},
            "previous": [],
            "next": [],
        }
        ctx = engine.expand_context("chunk1")
        assert "center" in ctx

    def test_enriches_with_document(self, engine, mock_neo4j):
        mock_neo4j.get_chunk_context.return_value = {
            "center": {"id": "chunk1", "text": "center"},
            "previous": [],
            "next": [],
        }
        ctx = engine.expand_context("chunk1")
        assert "document" in ctx

    def test_returns_empty_when_no_context(self, engine, mock_neo4j):
        mock_neo4j.get_chunk_context.return_value = None
        ctx = engine.expand_context("nonexistent")
        assert ctx == {}

    def test_handles_exception(self, engine, mock_neo4j):
        mock_neo4j.get_chunk_context.side_effect = Exception("error")
        ctx = engine.expand_context("chunk1")
        assert ctx == {}


# ---------------------------------------------------------------------------
# get_document_with_chunks
# ---------------------------------------------------------------------------


class TestGetDocumentWithChunks:
    """Tests for full document retrieval."""

    def test_returns_document_with_chunks(self, engine, mock_neo4j):
        result = engine.get_document_with_chunks("doc1")
        assert "chunks" in result
        assert result["id"] == "doc1"

    def test_returns_empty_when_not_found(self, engine, mock_neo4j):
        mock_neo4j.get_document_by_id.return_value = None
        result = engine.get_document_with_chunks("missing")
        assert result == {}


# ---------------------------------------------------------------------------
# suggest_related
# ---------------------------------------------------------------------------


class TestSuggestRelated:
    """Tests for related document suggestions."""

    def test_delegates_to_neo4j(self, engine, mock_neo4j):
        mock_neo4j.get_related_documents.return_value = [{"id": "doc2"}]
        results = engine.suggest_related("doc1")
        assert len(results) == 1

    def test_handles_exception(self, engine, mock_neo4j):
        mock_neo4j.get_related_documents.side_effect = Exception("error")
        results = engine.suggest_related("doc1")
        assert results == []


# ---------------------------------------------------------------------------
# get_all_categories / get_statistics
# ---------------------------------------------------------------------------


class TestUtilityMethods:
    """Tests for category listing and statistics."""

    def test_get_all_categories(self, engine):
        cats = engine.get_all_categories()
        assert "test" in cats
        assert "docs" in cats

    def test_get_all_categories_handles_exception(self, engine, mock_neo4j):
        mock_neo4j.get_all_categories.side_effect = Exception("error")
        cats = engine.get_all_categories()
        assert cats == []

    def test_get_statistics(self, engine):
        stats = engine.get_statistics()
        assert "neo4j" in stats
        assert "qdrant" in stats
        assert stats["neo4j"]["document_count"] == 5

    def test_get_statistics_handles_exception(self, engine, mock_neo4j):
        mock_neo4j.get_statistics.side_effect = Exception("error")
        stats = engine.get_statistics()
        assert stats == {}
