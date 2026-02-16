# GraphRAG Model Context Protocol 統合ガイド

このガイドでは、ハイブリッド Neo4j と Qdrant データベースシステムをクエリできる Model Context Protocol（MCP）コンポーネントの開発方法を詳しく説明します。この統合により、セマンティック検索機能とグラフベースのコンテキスト拡張を組み合わせた強力なドキュメント検索が可能になります。

> **注意**: MCP（Model Context Protocol）は、外部データソースへの構造化されたアクセスを提供するために大規模言語モデル（LLM）と統合するツールを構築するためのフレームワークです。

## システムアーキテクチャ概要

GraphRAG システムは以下を組み合わせています：

1. **Neo4j グラフデータベース**: ドキュメントの関係性、カテゴリ、メタデータを保存
2. **Qdrant ベクトルデータベース**: セマンティック検索用のドキュメントチャンクエンベディングを保存

このハイブリッドアプローチにより以下が可能になります：
- セマンティック類似検索（意味に基づくコンテンツの検索）
- グラフベースのコンテキスト拡張（関連ドキュメントの検索）
- ドキュメントカテゴリやその他のメタデータに基づくフィルタリング検索

## 接続パラメータ

### 検証済みデータベースエンドポイント

| データベース | サービス | ポート | 認証 |
|----------|---------|------|---------------|
| Neo4j    | HTTP    | 7474 | neo4j/password |
| Neo4j    | Bolt    | 7687 | neo4j/password |
| Qdrant   | HTTP    | 6333 | なし（デフォルト） |

### 環境変数

MCP サーバーの設定で以下の環境変数を使用してください：

```
# Neo4j 設定
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Qdrant 設定
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=document_chunks
```

## MCP ツール実装

### DocumentationGPTTool クラス

以下は GraphRAG システムをクエリできる Model Context Protocol ツールのサンプル実装です：

```python
import os
from typing import Dict, List, Optional, Any, Union
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

class DocumentationGPTTool:
    """GraphRAG ドキュメントシステムをクエリする MCP ツール"""

    def __init__(self):
        # Neo4j 接続
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        self.neo4j_driver = None

        # Qdrant 接続
        self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        self.qdrant_collection = os.getenv("QDRANT_COLLECTION", "document_chunks")
        self.qdrant_client = None

        # エンベディングモデル
        self.model_name = "all-MiniLM-L6-v2"
        self.model = None

        # 接続を初期化
        self._connect()

    def _connect(self):
        """Neo4j と Qdrant への接続を確立"""
        # Neo4j に接続
        try:
            self.neo4j_driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            # 接続テスト
            with self.neo4j_driver.session() as session:
                result = session.run("MATCH (d:Document) RETURN count(d) AS count")
                record = result.single()
                print(f"Connected to Neo4j with {record['count']} documents")
        except Exception as e:
            print(f"Neo4j connection error: {e}")

        # Qdrant に接続
        try:
            # バージョン互換性の問題に対応
            try:
                self.qdrant_client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
                collection_info = self.qdrant_client.get_collection(self.qdrant_collection)

                # クライアントバージョンに応じたベクトル数の確認
                vectors_count = 0
                if hasattr(collection_info, 'vectors_count'):
                    vectors_count = collection_info.vectors_count
                elif hasattr(collection_info, 'points_count'):
                    vectors_count = collection_info.points_count
                else:
                    # 観測されたバリエーションに基づいて設定構造を探索
                    try:
                        if hasattr(collection_info.config, 'params'):
                            if hasattr(collection_info.config.params, 'vectors'):
                                vectors_count = collection_info.config.params.vectors.size
                    except:
                        pass

                print(f"Connected to Qdrant collection '{self.qdrant_collection}' with {vectors_count} vectors")
            except Exception as e:
                print(f"Qdrant connection warning: {e}")
                # 必要に応じて古いバージョン向けのフォールバック
        except Exception as e:
            print(f"Qdrant connection error: {e}")

        # エンベディングモデルを読み込み
        try:
            self.model = SentenceTransformer(self.model_name)
            print(f"Loaded embedding model: {self.model_name}")
        except Exception as e:
            print(f"Error loading embedding model: {e}")

    def search_documentation(self, query: str, limit: int = 5, category: Optional[str] = None) -> Dict[str, Any]:
        """
        セマンティック検索を使用してドキュメントを検索し、オプションでグラフコンテキストで拡張します。

        Args:
            query: 検索クエリ
            limit: 返す結果の最大数
            category: オプションのカテゴリフィルター

        Returns:
            検索結果と関連ドキュメントを含む辞書
        """
        results = {
            "query": query,
            "chunks": [],
            "related_documents": []
        }

        # クエリ用のエンベディングを生成
        if self.model is None:
            try:
                self.model = SentenceTransformer(self.model_name)
            except Exception as e:
                results["error"] = f"Failed to load embedding model: {e}"
                return results

        query_embedding = self.model.encode(query)

        # Qdrant を検索
        try:
            # 検索 API のバージョン互換性に対応
            try:
                # 新しいバージョンは query_vector を使用
                search_result = self.qdrant_client.search(
                    collection_name=self.qdrant_collection,
                    query_vector=query_embedding.tolist(),
                    limit=limit
                )
            except TypeError:
                # 古いバージョンは vector パラメータを使用
                search_result = self.qdrant_client.search(
                    collection_name=self.qdrant_collection,
                    vector=query_embedding.tolist(),
                    limit=limit
                )

            # 検索結果をレスポンスに追加
            for result in search_result:
                # ID とスコアを抽出
                chunk_id = result.id
                score = result.score

                # ペイロードからテキストコンテンツを取得
                text = ""
                if hasattr(result, 'payload') and 'text' in result.payload:
                    text = result.payload['text']

                results["chunks"].append({
                    "chunk_id": chunk_id,
                    "text": text,
                    "score": score
                })
        except Exception as e:
            results["error"] = f"Qdrant search error: {e}"

        # Neo4j から関連ドキュメントで拡張
        if self.neo4j_driver and len(results["chunks"]) > 0:
            try:
                with self.neo4j_driver.session() as session:
                    # これらのチャンクを含むドキュメントと
                    # その関連ドキュメントを検索するクエリを構築
                    chunk_ids = [chunk["chunk_id"] for chunk in results["chunks"]]

                    cypher_query = """
                    MATCH (c:Chunk)
                    WHERE c.id IN $chunk_ids
                    MATCH (c)-[:PART_OF]->(d:Document)
                    OPTIONAL MATCH (d)-[:RELATED_TO]->(related:Document)
                    WITH DISTINCT d, related
                    RETURN d.id as doc_id, d.title as title,
                           collect(DISTINCT {doc_id: related.id, title: related.title}) as related_docs
                    """

                    if category:
                        cypher_query = """
                        MATCH (c:Chunk)
                        WHERE c.id IN $chunk_ids
                        MATCH (c)-[:PART_OF]->(d:Document)-[:HAS_CATEGORY]->(cat:Category {name: $category})
                        OPTIONAL MATCH (d)-[:RELATED_TO]->(related:Document)
                        WITH DISTINCT d, related
                        RETURN d.id as doc_id, d.title as title,
                               collect(DISTINCT {doc_id: related.id, title: related.title}) as related_docs
                        """

                    result = session.run(cypher_query, chunk_ids=chunk_ids, category=category)

                    # 結果を処理
                    related_docs = set()
                    for record in result:
                        doc_id = record["doc_id"]
                        title = record["title"]

                        # ドキュメント自体を追加
                        results["related_documents"].append({
                            "doc_id": doc_id,
                            "title": title
                        })

                        # 関連ドキュメントを追加
                        for related in record["related_docs"]:
                            if related["doc_id"] not in related_docs:
                                related_docs.add(related["doc_id"])
                                results["related_documents"].append({
                                    "doc_id": related["doc_id"],
                                    "title": related["title"]
                                })

                                # 関連ドキュメントの数を制限
                                if len(related_docs) >= limit:
                                    break

            except Exception as e:
                results["error"] = f"Neo4j query error: {e}"

        return results
```

### MCP 設定

Model Context Protocol サーバーのツール設定にツールを登録します：

```python
from documentation_tool import DocumentationGPTTool

def register_documentation_tool():
    return {
        "name": "documentation_search",
        "description": "Search the documentation for information about the GraphRAG system",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant documentation"
                },
                "category": {
                    "type": "string",
                    "description": "Optional category to filter results (e.g., 'setup', 'api', 'usage')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)"
                }
            },
            "required": ["query"]
        },
        "implementation": DocumentationGPTTool().search_documentation
    }
```

## エラーハンドリングの考慮事項

Model Context Protocol で GraphRAG を実装する際は、以下のエラーハンドリング戦略を含めてください：

1. **データベース接続障害**:
   - 指数バックオフ付きの接続リトライロジックを実装
   - 接続の問題に対する意味のあるエラーメッセージを提供

2. **バージョン互換性の問題**:
   - Qdrant API の違いに対応（サンプルコードに示す通り）
   - 異なる Neo4j APOC バージョンのフォールバックを提供

3. **クエリタイムアウトの処理**:
   - Neo4j と Qdrant の両方のクエリに適切なタイムアウトを設定
   - パフォーマンス低下時のサーキットブレーカーを実装

4. **コンテンツが見つからない場合**:
   - 検索結果がない場合に有用なメッセージを返す
   - 部分一致に基づいて関連トピックを提案

## 実装のテスト

提供されたクエリテスターを使用して MCP ツールの実装をテストできます：

```bash
# テストスクリプトを実行
uv run python scripts/testing/query_tester.py
```

## 高度な統合テクニック

### ハイブリッド検索の実装

より高度な検索機能を実現するには、ベクトル類似度スコアとグラフベースの関連性を組み合わせたハイブリッド検索を実装します：

```python
def hybrid_search(self, query: str, limit: int = 5, category: Optional[str] = None,
                  expand_context: bool = True) -> Dict[str, Any]:
    """
    ベクトル類似性とグラフコンテキストの両方を使用したハイブリッド検索を実行します。

    Args:
        query: 検索クエリ
        limit: 最大結果数
        category: オプションのカテゴリフィルター
        expand_context: グラフコンテキストで結果を拡張するかどうか

    Returns:
        統合された検索結果
    """
    # ベクトル検索の結果を取得
    vector_results = self.search_documentation(query, limit=limit*2, category=category)

    # コンテキスト拡張が不要な場合、ベクトル結果を返す
    if not expand_context:
        return vector_results

    # ベクトル結果からドキュメント ID を抽出
    doc_ids = [doc["doc_id"] for doc in vector_results.get("related_documents", [])]

    # グラフコンテキストで拡張
    try:
        with self.neo4j_driver.session() as session:
            cypher_query = """
            MATCH (d:Document)
            WHERE d.id IN $doc_ids
            OPTIONAL MATCH (d)-[:RELATED_TO*1..2]->(related:Document)
            WITH related, d
            WHERE related IS NOT NULL AND related.id NOT IN $doc_ids
            RETURN DISTINCT related.id as doc_id, related.title as title,
                   count(*) as relevance_score
            ORDER BY relevance_score DESC
            LIMIT $limit
            """

            result = session.run(cypher_query, doc_ids=doc_ids, limit=limit)

            # 拡張された結果を追加
            for record in result:
                vector_results["related_documents"].append({
                    "doc_id": record["doc_id"],
                    "title": record["title"],
                    "graph_score": record["relevance_score"]
                })
    except Exception as e:
        vector_results["error"] = f"Graph expansion error: {e}"

    return vector_results
```

## トラブルシューティング

### よくある問題と解決策

1. **接続拒否**:
   - 正しいポートを確認: Neo4j は 7687（Bolt）、Qdrant は 6333
   - 各サービスが実行中であることを確認

2. **認証失敗**:
   - Neo4j の認証情報を確認（デフォルト: neo4j/password）
   - 環境変数が正しく設定されていることを確認

3. **Qdrant バージョン互換性**:
   - 非推奨メソッドに関するクライアント警告は想定内
   - サンプルに示されたバージョン対応コードを使用

4. **空の検索結果**:
   - Qdrant コレクション名を確認（デフォルト: document_chunks）
   - エンベディングモデルがインデックス作成時に使用したものと一致しているか確認

## リソース

- [Neo4j Python Driver Documentation](https://neo4j.com/docs/api/python-driver/current/)
- [Qdrant Python Client Documentation](https://qdrant.tech/documentation/quick-start/)
- [Sentence-Transformers Documentation](https://www.sbert.net/)

テストレポートと接続情報の詳細については、[データベース接続テスト](../test_db_connection/index.md)を参照してください。
