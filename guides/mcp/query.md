# GraphRAG クエリ実装

このガイドでは、GraphRAG システムと連携する MCP ツールにクエリ機能を実装する方法を説明します。

## クエリフロー

クエリプロセスは以下のステップで構成されます：

1. クエリテキストのエンベディングを生成
2. Qdrant で類似ベクトルを検索
3. Neo4j から関連ドキュメントを取得
4. 結果を統合してランキング

## 実装

### 1. クエリクラス

```python
from typing import List, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer

class GraphRAGQuery:
    def __init__(self, manager, model_name="all-MiniLM-L6-v2"):
        self.manager = manager
        self.embedding_model = SentenceTransformer(model_name)

    def generate_embedding(self, text: str) -> np.ndarray:
        """クエリテキストのエンベディングベクトルを生成"""
        return self.embedding_model.encode(text)

    async def search(self, query: str, limit: int = 5) -> List[Dict[Any, Any]]:
        """Qdrant と Neo4j の両方を使用したハイブリッド検索を実行"""
        # クエリエンベディングを生成
        query_vector = self.generate_embedding(query)

        # Qdrant を検索
        qdrant_results = self.search_qdrant(query_vector, limit)

        # Neo4j から関連ドキュメントを取得
        neo4j_results = self.expand_context(qdrant_results)

        # 結果を統合してランキング
        final_results = self.rank_results(query, qdrant_results, neo4j_results)

        return final_results

    def search_qdrant(self, query_vector: np.ndarray, limit: int) -> List[Dict[Any, Any]]:
        """Qdrant で類似ベクトルを検索"""
        try:
            results = self.manager.qdrant.client.search(
                collection_name=self.manager.collection_name,
                query_vector=query_vector.tolist(),
                limit=limit
            )
            return [
                {
                    'doc_id': hit.payload.get('doc_id'),
                    'score': hit.score,
                    'category': hit.payload.get('category')
                }
                for hit in results
            ]
        except Exception as e:
            print(f"Qdrant search error: {str(e)}")
            return []

    def expand_context(self, qdrant_results: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Neo4j から関連ドキュメントを取得"""
        doc_ids = [result['doc_id'] for result in qdrant_results]

        try:
            with self.manager.neo4j.driver.session() as session:
                query = """
                MATCH (d:Document)
                WHERE d.doc_id IN $doc_ids
                OPTIONAL MATCH (d)-[r]-(related)
                RETURN d.doc_id as doc_id,
                       d.title as title,
                       d.content as content,
                       collect(DISTINCT {
                           type: type(r),
                           doc_id: related.doc_id,
                           title: related.title
                       }) as related_docs
                """
                result = session.run(query, doc_ids=doc_ids)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"Neo4j query error: {str(e)}")
            return []

    def rank_results(self, query: str,
                    qdrant_results: List[Dict[Any, Any]],
                    neo4j_results: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """両データベースの結果を統合してランキング"""
        # doc_id から Neo4j 結果へのマッピングを作成
        neo4j_map = {doc['doc_id']: doc for doc in neo4j_results}

        # 結果を統合
        ranked_results = []
        for qdrant_hit in qdrant_results:
            doc_id = qdrant_hit['doc_id']
            if doc_id in neo4j_map:
                neo4j_doc = neo4j_map[doc_id]
                ranked_results.append({
                    'doc_id': doc_id,
                    'title': neo4j_doc['title'],
                    'content': neo4j_doc['content'],
                    'score': qdrant_hit['score'],
                    'category': qdrant_hit['category'],
                    'related_docs': neo4j_doc['related_docs']
                })

        return ranked_results
```

### 2. MCP ツール実装

GraphRAG 機能を MCP ツールとして実装する方法：

```python
from typing import Optional, Dict, Any
from mcp.tools import BaseTool

class GraphRAGTool(BaseTool):
    name = "GraphRAG"
    description = "Search through documents using hybrid Neo4j and Qdrant search"

    def __init__(self):
        super().__init__()
        self.manager = GraphRAGManager(
            neo4j_uri=NEO4J_URI,
            neo4j_user=NEO4J_USER,
            neo4j_password=NEO4J_PASSWORD,
            qdrant_host=QDRANT_HOST,
            qdrant_port=QDRANT_PORT,
            collection_name=QDRANT_COLLECTION
        )
        self.query_engine = GraphRAGQuery(self.manager)

    async def execute(self, query: str,
                     limit: Optional[int] = 5,
                     category: Optional[str] = None) -> Dict[str, Any]:
        """検索クエリを実行"""
        try:
            results = await self.query_engine.search(query, limit)

            # カテゴリが指定されている場合はフィルタリング
            if category:
                results = [r for r in results if r['category'] == category]

            return {
                'status': 'success',
                'results': results,
                'count': len(results)
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

    def cleanup(self):
        """データベース接続をクリーンアップ"""
        self.manager.close()
```

## 使用例

MCP 環境で GraphRAG ツールを使用する方法：

```python
# ツールを初期化
graphrag_tool = GraphRAGTool()

# 検索を実行
results = await graphrag_tool.execute(
    query="How to configure Neo4j authentication?",
    limit=5,
    category="setup"
)

# 結果を処理
if results['status'] == 'success':
    for doc in results['results']:
        print(f"Document: {doc['title']}")
        print(f"Score: {doc['score']}")
        print(f"Related docs: {len(doc['related_docs'])}")
        print("---")
else:
    print(f"Error: {results['error']}")

# クリーンアップ
graphrag_tool.cleanup()
```

## クエリパラメータ

- `query` (str): 検索クエリテキスト
- `limit` (int, オプション): 最大結果数（デフォルト: 5）
- `category` (str, オプション): カテゴリによる結果フィルタリング

## レスポンスフォーマット

検索結果は以下のフォーマットで返されます：

```python
{
    'status': 'success',
    'results': [
        {
            'doc_id': str,
            'title': str,
            'content': str,
            'score': float,
            'category': str,
            'related_docs': [
                {
                    'type': str,
                    'doc_id': str,
                    'title': str
                }
            ]
        }
    ],
    'count': int
}
```

## エラーハンドリング

クエリエラーとエッジケースの処理について詳しくは、[エラーハンドリング](error_handling.md)を参照してください。
