"""
Entity and relationship extractor using Gemini 2.5 Flash.
Extracts structured entities and relationships from text chunks
for building a knowledge graph in Neo4j.
"""

import json
import logging
import os
import time
from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# --- Pydantic schemas for structured output ---

class ExtractedEntity(BaseModel):
    name: str
    type: str  # Person, Organization, Concept, Technology, Event, Location
    description: str


class ExtractedRelation(BaseModel):
    source: str  # entity name
    target: str  # entity name
    relation: str  # e.g. "developed", "is_part_of", "uses"


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]


# --- Main extractor class ---

EXTRACTION_PROMPT = """\
以下のテキストから、重要なエンティティ（実体）とそれらの間の関係性を抽出してください。

## エンティティの種類
- Person: 人物名
- Organization: 組織名、企業名、団体名
- Concept: 抽象的な概念、理論、手法
- Technology: 技術、ツール、プログラミング言語、フレームワーク
- Event: イベント、出来事
- Location: 場所、地域

## ルール
- 具体的で重要なエンティティのみ抽出すること（一般的すぎる語は除外）
- エンティティ名は正式名称を使用すること
- 関係性は簡潔な動詞または前置詞句で表現すること（例: "開発した", "の一部である", "を使用する"）
- 同一エンティティは統一した名前で表記すること

## テキスト
{text}
"""


class EntityExtractor:
    """Extract entities and relationships from text using Gemini 2.5 Flash."""

    def __init__(self, config):
        api_key = config.get("gemini.api_key", os.getenv("GEMINI_API_KEY", ""))
        if not api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")

        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"
        self.max_retries = 3
        self.base_delay = 1.0  # seconds

    def extract_from_chunk(self, text: str) -> Optional[ExtractionResult]:
        """Extract entities and relationships from a single text chunk.

        Returns None if extraction fails after retries.
        """
        if not text or not text.strip():
            return None

        prompt = EXTRACTION_PROMPT.format(text=text)

        for attempt in range(self.max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ExtractionResult,
                        temperature=0,
                    ),
                )

                if response.parsed:
                    return response.parsed

                # Fallback: parse from text
                if response.text:
                    data = json.loads(response.text)
                    return ExtractionResult(**data)

                logger.warning(f"Empty response from Gemini (attempt {attempt + 1})")

            except Exception as e:
                delay = self.base_delay * (2 ** attempt)
                logger.warning(
                    f"Gemini API error (attempt {attempt + 1}/{self.max_retries}): {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)

        logger.error(f"Failed to extract entities after {self.max_retries} attempts")
        return None

    def extract_from_chunks(
        self, chunks: list[dict], progress_callback=None
    ) -> dict:
        """Extract entities and relationships from multiple chunks.

        Args:
            chunks: List of chunk dicts with 'id', 'text', 'doc_id' keys.
            progress_callback: Optional callable(current, total) for progress.

        Returns:
            Dict with 'entities', 'relations', 'chunk_entity_map' keys.
        """
        all_entities: dict[str, ExtractedEntity] = {}
        all_relations: list[dict] = []
        chunk_entity_map: list[dict] = []  # chunk_id -> entity_names

        total = len(chunks)
        for idx, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(idx, total)

            result = self.extract_from_chunk(chunk["text"])
            if not result:
                continue

            chunk_id = chunk["id"]
            doc_id = chunk["doc_id"]

            # Collect entities (deduplicate by normalized name)
            for entity in result.entities:
                key = self._normalize_name(entity.name)
                if key not in all_entities:
                    all_entities[key] = entity
                # Map chunk -> entity
                chunk_entity_map.append({
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "entity_name": key,
                })

            # Collect relations (normalize source/target names)
            for rel in result.relations:
                source_key = self._normalize_name(rel.source)
                target_key = self._normalize_name(rel.target)
                if source_key in all_entities and target_key in all_entities:
                    all_relations.append({
                        "source": source_key,
                        "target": target_key,
                        "relation": rel.relation,
                    })

        if progress_callback:
            progress_callback(total, total)

        # Convert entities to list of dicts
        entity_list = [
            {
                "name": name,
                "type": entity.type,
                "description": entity.description,
            }
            for name, entity in all_entities.items()
        ]

        logger.info(
            f"Extracted {len(entity_list)} entities and "
            f"{len(all_relations)} relations from {total} chunks"
        )

        return {
            "entities": entity_list,
            "relations": all_relations,
            "chunk_entity_map": chunk_entity_map,
        }

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize entity name for deduplication."""
        return name.strip().lower()

    @staticmethod
    def is_available(config) -> bool:
        """Check if Gemini API key is configured."""
        api_key = config.get("gemini.api_key", os.getenv("GEMINI_API_KEY", ""))
        return bool(api_key)
