"""Shared test fixtures for graphrag-hybrid test suite."""

import pytest


class MockConfig:
    """Lightweight config mock for unit tests.

    Mimics the ``Config.get(key, default)`` dot-notation interface used
    throughout the codebase without requiring pydantic-settings or
    environment variables.
    """

    def __init__(self, overrides=None):
        self._data = {
            "neo4j": {
                "uri": "bolt://localhost:7687",
                "user": "neo4j",
                "password": "test",
                "database": "neo4j",
            },
            "qdrant": {
                "host": "localhost",
                "port": 6333,
                "grpc_port": 6334,
                "collection": "test_chunks",
                "prefer_grpc": False,
            },
            "embedding": {
                "model_name": "intfloat/multilingual-e5-base",
                "vector_size": 768,
                "device": "cpu",
                "max_length": 512,
            },
            "chunking": {
                "chunk_size": 800,
                "chunk_overlap": 150,
            },
            "gemini": {
                "api_key": "",
            },
        }
        if overrides:
            for k, v in overrides.items():
                keys = k.split(".")
                d = self._data
                for key in keys[:-1]:
                    d = d.setdefault(key, {})
                d[keys[-1]] = v

    def get(self, key, default=None):
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value


@pytest.fixture
def mock_config():
    """Return a MockConfig with test defaults."""
    return MockConfig()


@pytest.fixture
def sample_markdown():
    """Sample markdown content with YAML frontmatter."""
    return (
        "---\n"
        "title: テストドキュメント\n"
        "category: test/unit\n"
        "---\n"
        "# テスト見出し\n\n"
        "これは最初の段落です。内容がここに入ります。\n\n"
        "二番目の段落です。追加の情報を含みます。"
    )


@pytest.fixture
def sample_chunks():
    """List of chunk dicts matching the pipeline output schema."""
    return [
        {
            "id": "chunk-001",
            "text": "これはテストチャンクです。内容がここに入ります。",
            "doc_id": "doc-001",
            "position": 0,
        },
        {
            "id": "chunk-002",
            "text": "二番目のチャンクです。追加の情報を含みます。",
            "doc_id": "doc-001",
            "position": 1,
        },
        {
            "id": "chunk-003",
            "text": "三番目のチャンクです。最後の部分です。",
            "doc_id": "doc-001",
            "position": 2,
        },
    ]
