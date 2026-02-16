# GraphRAG 使用例

このガイドでは、さまざまなシナリオでの GraphRAG システムの実用的な使用例を紹介します。

## 基本的な検索の例

```python
from graphrag import GraphRAGTool

async def basic_search():
    # ツールを初期化
    tool = GraphRAGTool()

    try:
        # シンプルな検索を実行
        results = await tool.execute(
            query="How to configure Neo4j authentication?",
            limit=5
        )

        # 結果を処理
        if results['status'] == 'success':
            for doc in results['results']:
                print(f"Title: {doc['title']}")
                print(f"Score: {doc['score']:.4f}")
                print(f"Content: {doc['content'][:200]}...")
                print("---")
    finally:
        tool.cleanup()
```

## カテゴリフィルター付き検索

```python
async def category_search():
    tool = GraphRAGTool()

    try:
        # 特定のカテゴリ内で検索
        results = await tool.execute(
            query="How to set up replication?",
            category="deployment",
            limit=3
        )

        if results['status'] == 'success':
            print(f"Found {results['count']} results:")
            for doc in results['results']:
                print(f"Category: {doc['category']}")
                print(f"Title: {doc['title']}")
                print("---")
    finally:
        tool.cleanup()
```

## 関連ドキュメント検索

```python
async def related_docs_search():
    tool = GraphRAGTool()

    try:
        # 関連ドキュメント付きで検索
        results = await tool.execute(
            query="Neo4j backup strategies",
            limit=2
        )

        if results['status'] == 'success':
            for doc in results['results']:
                print(f"Main Document: {doc['title']}")
                print("\nRelated Documents:")
                for related in doc['related_docs']:
                    print(f"- {related['title']} ({related['type']})")
                print("---")
    finally:
        tool.cleanup()
```

## エラーハンドリングの例

```python
from graphrag import GraphRAGTool, ErrorLogger

async def robust_search():
    tool = GraphRAGTool()
    logger = ErrorLogger()

    try:
        # リトライ付きで検索を試行
        for attempt in range(3):
            try:
                results = await tool.execute(
                    query="Database optimization techniques"
                )
                if results['status'] == 'success':
                    return results
            except Exception as e:
                logger.log_error(e, {
                    'attempt': attempt + 1,
                    'operation': 'search'
                })
                if attempt < 2:
                    print(f"Retrying... (attempt {attempt + 2}/3)")
                    await asyncio.sleep(1)
                else:
                    print("All attempts failed")
                    return None
    finally:
        tool.cleanup()
```

## ヘルスチェックの例

```python
from graphrag import GraphRAGTool, HealthCheck

async def system_health_check():
    tool = GraphRAGTool()
    health_checker = HealthCheck(tool.manager)

    try:
        # システムの正常性をチェック
        status = await health_checker.check_health()

        print("System Health Status:")
        print(f"Timestamp: {status['timestamp']}")

        # Neo4j のステータス
        print("\nNeo4j:")
        print(f"Status: {status['neo4j']['status']}")
        if 'message' in status['neo4j']:
            print(f"Message: {status['neo4j']['message']}")
        elif 'error' in status['neo4j']:
            print(f"Error: {status['neo4j']['error']}")

        # Qdrant のステータス
        print("\nQdrant:")
        print(f"Status: {status['qdrant']['status']}")
        if status['qdrant']['status'] == 'healthy':
            print(f"Vectors: {status['qdrant']['vectors_count']}")
        elif 'error' in status['qdrant']:
            print(f"Error: {status['qdrant']['error']}")
    finally:
        tool.cleanup()
```

## バッチ処理の例

```python
from graphrag import GraphRAGTool
from typing import List

async def batch_search(queries: List[str]):
    tool = GraphRAGTool()

    try:
        results = []
        for query in queries:
            # 各クエリの検索を実行
            response = await tool.execute(query=query)
            if response['status'] == 'success':
                results.append({
                    'query': query,
                    'results': response['results']
                })
            else:
                print(f"Failed query: {query}")
                print(f"Error: {response.get('error')}")

        return results
    finally:
        tool.cleanup()

# 使用例
queries = [
    "Neo4j backup strategies",
    "Qdrant optimization techniques",
    "Database security best practices"
]

results = await batch_search(queries)
for item in results:
    print(f"\nQuery: {item['query']}")
    print(f"Found {len(item['results'])} results")
```

## カスタムランキングの例

```python
from graphrag import GraphRAGTool
from typing import List, Dict, Any

class CustomRankedSearch:
    def __init__(self):
        self.tool = GraphRAGTool()

    def rank_results(self, results: List[Dict[Any, Any]],
                    weights: Dict[str, float]) -> List[Dict[Any, Any]]:
        """カスタムランキング関数"""
        for result in results:
            # 重み付きスコアを計算
            score = result['score'] * weights.get('similarity', 1.0)

            # 関連ドキュメント数に基づいてスコアを調整
            related_count = len(result['related_docs'])
            score += related_count * weights.get('relations', 0.1)

            # カテゴリに基づいてスコアを調整
            if result['category'] == weights.get('preferred_category'):
                score *= weights.get('category_boost', 1.2)

            result['adjusted_score'] = score

        # 調整済みスコアでソート
        return sorted(results, key=lambda x: x['adjusted_score'], reverse=True)

    async def search(self, query: str, weights: Dict[str, float]):
        try:
            # 基本検索を実行
            response = await self.tool.execute(query=query, limit=10)

            if response['status'] == 'success':
                # カスタムランキングを適用
                ranked_results = self.rank_results(
                    response['results'],
                    weights
                )
                return {
                    'status': 'success',
                    'results': ranked_results[:5]  # 上位5件を返す
                }
            return response
        finally:
            self.tool.cleanup()

# 使用例
weights = {
    'similarity': 1.0,      # ベース類似度スコアの重み
    'relations': 0.1,       # 関連ドキュメントの重み
    'category_boost': 1.2,  # 優先カテゴリのブースト
    'preferred_category': 'setup'
}

searcher = CustomRankedSearch()
results = await searcher.search(
    "Database configuration",
    weights
)
```

## MCP サーバーとの統合

```python
from mcp.tools import BaseTool
from graphrag import GraphRAGTool

class GraphRAGMCPTool(BaseTool):
    name = "GraphRAG"
    description = "Search through documentation using GraphRAG"

    def __init__(self):
        super().__init__()
        self.tool = GraphRAGTool()

    async def execute(self, query: str, **kwargs):
        try:
            # パラメータを抽出
            limit = kwargs.get('limit', 5)
            category = kwargs.get('category')

            # 検索を実行
            results = await self.tool.execute(
                query=query,
                limit=limit,
                category=category
            )

            # MCP 用にレスポンスをフォーマット
            if results['status'] == 'success':
                return {
                    'success': True,
                    'data': {
                        'results': results['results'],
                        'count': results['count']
                    }
                }
            else:
                return {
                    'success': False,
                    'error': results.get('error', 'Unknown error')
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            self.tool.cleanup()

    def cleanup(self):
        """ツールのアンロード時にリソースをクリーンアップ"""
        if hasattr(self, 'tool'):
            self.tool.cleanup()
```

## サンプルの実行方法

これらのサンプルを実行するには：

1. Neo4j と Qdrant の両方が実行中であることを確認
2. 必要なパッケージをインストール：
   ```bash
   uv add neo4j qdrant-client sentence-transformers
   ```
3. 環境変数を設定するか、接続パラメータを更新
4. サンプルを実行：
   ```python
   import asyncio

   async def main():
       # 基本検索
       await basic_search()

       # カテゴリ検索
       await category_search()

       # ヘルスチェック
       await system_health_check()

   if __name__ == "__main__":
       asyncio.run(main())
   ```

詳細な設定方法については、[接続セットアップ](connection.md)を参照してください。
