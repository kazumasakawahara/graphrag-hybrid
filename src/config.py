"""
Configuration management for GraphRAG

Uses pydantic-settings for validated, environment-aware configuration
with backward-compatible dot-notation access.
"""

import logging
from typing import Any, Optional

from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Neo4jSettings(BaseSettings):
    """Neo4j connection settings."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"

    model_config = {"env_prefix": "NEO4J_"}


class QdrantSettings(BaseSettings):
    """Qdrant connection settings."""

    host: str = "localhost"
    port: int = 6333
    grpc_port: int = 6334
    collection: str = "document_chunks"
    prefer_grpc: bool = True

    model_config = {"env_prefix": "QDRANT_"}


class EmbeddingSettings(BaseSettings):
    """Embedding model settings.

    Supports both canonical names (model_name, vector_size) and
    aliases (model, dimension) for backward compatibility.
    """

    model_name: str = Field(
        "intfloat/multilingual-e5-base",
        alias="EMBEDDING_MODEL",
        validation_alias="EMBEDDING_MODEL",
    )
    vector_size: int = Field(
        768,
        alias="EMBEDDING_DIMENSION",
        validation_alias="EMBEDDING_DIMENSION",
    )
    device: str = "cpu"
    max_length: int = 512

    model_config = {"env_prefix": "EMBEDDING_", "populate_by_name": True}

    @property
    def model(self) -> str:
        """Alias for model_name (backward compatibility)."""
        return self.model_name

    @property
    def dimension(self) -> int:
        """Alias for vector_size (backward compatibility)."""
        return self.vector_size


class ChunkingSettings(BaseSettings):
    """Document chunking settings."""

    chunk_size: int = Field(800, alias="CHUNK_SIZE", validation_alias="CHUNK_SIZE")
    chunk_overlap: int = Field(
        150, alias="CHUNK_OVERLAP", validation_alias="CHUNK_OVERLAP"
    )

    model_config = {"populate_by_name": True}


class Config(BaseSettings):
    """Top-level application configuration.

    Loads values from environment variables automatically via
    pydantic-settings. Provides a backward-compatible ``get()``
    method for dot-notation access (e.g. ``config.get('neo4j.uri')``).
    """

    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)

    def get(self, key: str, default: Any = None) -> Any:
        """Backward-compatible dot-notation access.

        Examples:
            config.get('neo4j.uri')
            config.get('embedding.model_name')
        """
        keys = key.split(".")
        value: Any = self
        for k in keys:
            if isinstance(value, BaseSettings):
                value = getattr(value, k, None)
            elif isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a config value on the appropriate sub-model.

        Provided for backward compatibility. Prefer environment
        variables for configuration in production.
        """
        keys = key.split(".")
        target: Any = self
        for k in keys[:-1]:
            target = getattr(target, k, None)
            if target is None:
                return
        if target is not None:
            try:
                setattr(target, k if len(keys) == 1 else keys[-1], value)
            except (AttributeError, ValueError):
                logger.warning(f"Could not set config key: {key}")


# ---------------------------------------------------------------------------
# Module-level singleton and exports
# ---------------------------------------------------------------------------

config = Config()

NEO4J_URI: str = config.neo4j.uri
NEO4J_USER: str = config.neo4j.user
NEO4J_PASSWORD: str = config.neo4j.password

QDRANT_HOST: str = config.qdrant.host
QDRANT_PORT: int = config.qdrant.port
QDRANT_COLLECTION: str = config.qdrant.collection

EMBEDDING_MODEL: str = config.embedding.model_name
EMBEDDING_DIMENSION: int = config.embedding.vector_size
