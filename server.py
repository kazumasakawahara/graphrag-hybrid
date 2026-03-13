"""
GraphRAG Hybrid MCP Server
Neo4j + Qdrant ハイブリッド検索システムのMCPサーバー

日本語対応版:
  - Embedding: intfloat/multilingual-e5-base (768次元)
  - チャンキング: 日本語文境界ベース
  - E5プレフィックス: query/passage を自動付与

Usage:
    python server.py          # STDIO mode (Claude Desktop用)
    python server.py --http   # HTTP mode (開発・テスト用)
"""

import json
import logging
import os
import sys
from typing import Optional

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from fastmcp import FastMCP

# .envを読み込み
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === FastMCPサーバー作成 ===
mcp = FastMCP(
    "GraphRAG Hybrid Search",
    instructions=(
        "Neo4j グラフDB + Qdrant ベクトルDB のハイブリッド検索システムです。\n"
        "日本語・英語両対応。ドキュメントのセマンティック検索、カテゴリ検索、"
        "ハイブリッド検索が可能です。\n"
        "検索結果のコンテキスト拡張や関連ドキュメントの提案も行えます。"
    ),
)

# === GraphRAGツールのシングルトン管理 ===
_tool_instance = None


def _get_tool():
    """GraphRAGMCPToolのシングルトンインスタンスを取得"""
    global _tool_instance
    if _tool_instance is None:
        logger.info("Initializing GraphRAG MCP Tool...")
        from src.graphrag_mcp_tool import GraphRAGMCPTool
        _tool_instance = GraphRAGMCPTool()
        logger.info("GraphRAG MCP Tool initialized successfully")
    return _tool_instance


# === MCPツール定義 ===

@mcp.tool
def search(
    query: str,
    limit: int = 5,
    category: Optional[str] = None,
    search_type: str = "hybrid"
) -> str:
    """ドキュメントをハイブリッド検索します。

    Neo4j（グラフ構造）とQdrant（ベクトル類似度）を組み合わせた
    高精度なドキュメント検索を行います。日本語・英語両対応。

    Args:
        query: 検索クエリテキスト
        limit: 返す結果の最大数（デフォルト: 5）
        category: カテゴリでフィルタ（任意）
        search_type: 検索タイプ - "hybrid"（推奨）, "semantic", "category"

    Returns:
        検索結果のJSON文字列
    """
    tool = _get_tool()
    result = tool.search(
        query=query,
        limit=limit,
        category=category,
        search_type=search_type
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
def get_document(doc_id: str) -> str:
    """ドキュメントIDを指定して完全なドキュメントを取得します。

    Args:
        doc_id: 取得するドキュメントのID

    Returns:
        ドキュメント情報とチャンクのJSON文字列
    """
    tool = _get_tool()
    result = tool.get_document(doc_id)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
def expand_context(chunk_id: str, context_size: int = 2) -> str:
    """特定チャンクの前後のコンテキストを拡張取得します。

    検索結果の一部をより詳しく読みたい場合に使用します。

    Args:
        chunk_id: コンテキストを拡張するチャンクのID
        context_size: 前後に取得するチャンク数（デフォルト: 2）

    Returns:
        拡張コンテキストのJSON文字列
    """
    tool = _get_tool()
    result = tool.expand_context(chunk_id=chunk_id, context_size=context_size)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
def get_categories() -> str:
    """登録されている全ドキュメントカテゴリを取得します。

    Returns:
        カテゴリ一覧のJSON文字列
    """
    tool = _get_tool()
    result = tool.get_categories()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
def get_statistics() -> str:
    """システムの統計情報を取得します。

    Neo4jとQdrantの両方のデータベースの状態を表示します。

    Returns:
        統計情報のJSON文字列
    """
    tool = _get_tool()
    result = tool.get_statistics()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
def ingest_document(file_path: str) -> str:
    """新しいドキュメントをシステムに取り込みます。

    Markdownファイルを読み込み、日本語対応のチャンク分割を行い、
    Neo4jとQdrantの両方に登録します。

    Args:
        file_path: 取り込むドキュメントのファイルパス（.md）

    Returns:
        取り込み結果のJSON文字列
    """
    try:
        # ファイル存在確認
        if not os.path.exists(file_path):
            return json.dumps(
                {"error": f"ファイルが見つかりません: {file_path}"},
                ensure_ascii=False
            )

        tool = _get_tool()

        # DocumentProcessor を使用して日本語対応チャンク分割
        from src.config import Config
        from src.processors.document_processor import DocumentProcessor

        config = Config()
        doc_processor = DocumentProcessor(config)

        try:
            metadata, chunks = doc_processor.process_document(file_path)
        except ValueError as e:
            return json.dumps(
                {"error": f"未対応のファイル形式です: {str(e)}"},
                ensure_ascii=False
            )

        if not chunks:
            return json.dumps(
                {"error": "チャンクの生成に失敗しました"},
                ensure_ascii=False
            )

        # Neo4jに登録
        tool.neo4j_manager.import_document(
            doc_id=metadata['id'],
            title=metadata.get('title', ''),
            category=metadata.get('category', 'imported'),
            chunks=chunks,
            metadata={
                'source': file_path,
                'key_concepts': metadata.get('key_concepts', []),
            }
        )

        # Qdrantに登録（passage embedding が自動適用される）
        tool.qdrant_manager.import_chunks(chunks)

        result = {
            "status": "success",
            "document": {
                "id": metadata['id'],
                "title": metadata.get('title', ''),
                "category": metadata.get('category', 'imported'),
                "chunk_count": len(chunks),
                "file_path": file_path,
            }
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Error ingesting document: {str(e)}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool
def search_entities(
    query: str,
    limit: int = 10,
) -> str:
    """エンティティ名で検索します。

    ドキュメントから抽出されたエンティティ（人物、組織、概念、技術など）を
    名前で検索し、関連するチャンクとドキュメントを返します。

    Args:
        query: エンティティ名（部分一致）
        limit: 返す結果の最大数（デフォルト: 10）

    Returns:
        エンティティ検索結果のJSON文字列
    """
    tool = _get_tool()
    result = tool.search_entities(query=query, limit=limit)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
def get_entity_graph(entity_name: str) -> str:
    """エンティティの関連グラフを取得します。

    指定されたエンティティと、それに関連するエンティティや
    出現するドキュメントの情報を返します。

    Args:
        entity_name: エンティティ名（完全一致）

    Returns:
        エンティティグラフ情報のJSON文字列
    """
    tool = _get_tool()
    result = tool.get_entity_graph(entity_name=entity_name)
    return json.dumps(result, ensure_ascii=False, indent=2)


# === MCPリソース定義 ===

@mcp.resource("graphrag://status")
def system_status() -> str:
    """システムのステータスを返すリソース"""
    try:
        tool = _get_tool()
        stats = tool.get_statistics()
        status = {
            "status": "running",
            "neo4j": stats.get("neo4j", {}),
            "qdrant": stats.get("qdrant", {}),
        }
        return json.dumps(status, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps(
            {"status": "error", "message": str(e)}, ensure_ascii=False
        )


# === エントリーポイント ===

if __name__ == "__main__":
    if "--http" in sys.argv:
        # HTTP mode（開発・テスト用）
        mcp.run(transport="http", host="0.0.0.0", port=8100)
    else:
        # STDIO mode（Claude Desktop用）
        mcp.run()
