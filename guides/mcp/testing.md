# GraphRAG との MCP 統合テスト

このガイドでは、GraphRAG システムとの MCP 統合をテストして、適切な接続性と機能を確保する方法を説明します。

## 前提条件

- GraphRAG システムが起動・稼働していること
- Neo4j データベースにドキュメントが投入されていること
- Qdrant データベースにベクトルエンベディングが投入されていること
- DocumentationGPTTool が実装された MCP サーバー
- Python 3.8+ 環境

## 接続テスト

まず、MCP サーバーが両データベースに接続できることを確認します：

```python
import logging
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
import warnings

# ロギングを設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Qdrant バージョン警告を抑制
warnings.filterwarnings("ignore", category=UserWarning, module="qdrant_client")

def test_neo4j_connection():
    """検証済みポートで Neo4j への接続をテスト"""
    logger.info("Testing Neo4j connection...")


    uri = "bolt://localhost:7687"
    username = "neo4j"
    password = "password"

    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        with driver.session() as session:
            result = session.run("RETURN 'Neo4j connection successful' as message")
            logger.info(result.single()["message"])

            # ノード数をカウント
            count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            logger.info(f"Neo4j database contains {count} nodes")
        driver.close()
        return True
    except Exception as e:
        logger.error(f"Neo4j connection failed: {e}")
        return False

def test_qdrant_connection():
    """検証済みポートで Qdrant への接続をテスト"""
    logger.info("Testing Qdrant connection...")

    # 検証済みの非標準ポートを使用
    try:
        client = QdrantClient(host="localhost", port=6333)
        # シンプルな API コールで Qdrant の稼働を確認
        status = client.get_collections()
        logger.info(f"Qdrant connection successful. Collections: {len(status.collections)}")

        # document_chunks コレクションを確認
        if any(c.name == "document_chunks" for c in status.collections):
            collection_info = client.get_collection("document_chunks")
            logger.info(f"document_chunks collection info: {collection_info}")

            # ベクトル数を取得
            try:
                vectors_count = collection_info.vectors_count
                logger.info(f"Collection contains {vectors_count} vectors")
            except AttributeError:
                # 異なる Qdrant バージョンの代替属性名を試行
                if hasattr(collection_info, "vectors_count"):
                    logger.info(f"Collection contains {collection_info.vectors_count} vectors")
                elif hasattr(collection_info, "points_count"):
                    logger.info(f"Collection contains {collection_info.points_count} vectors")
                else:
                    logger.warning("Could not determine vector count - check Qdrant version compatibility")

        return True
    except Exception as e:
        logger.error(f"Qdrant connection failed: {e}")
        return False

def main():
    """すべての接続テストを実行"""
    logger.info("Starting connection tests...")

    neo4j_success = test_neo4j_connection()
    qdrant_success = test_qdrant_connection()

    if neo4j_success and qdrant_success:
        logger.info("\n✅ All database connections successful!")
    else:
        logger.error("\n❌ Some connections failed. Please check the logs above.")

if __name__ == "__main__":
    main()
```

## 機能テスト

接続を確認した後、MCP ツール実装の実際の機能をテストします：

```python
from your_mcp_package import DocumentationGPTTool

def test_search_functionality():
    """DocumentationGPTTool の検索機能をテスト"""
    print("Testing search functionality...")

    # ツールを初期化
    doc_tool = DocumentationGPTTool()

    # シンプルなクエリでテスト
    test_query = "database setup"
    print(f"Searching for: '{test_query}'")

    results = doc_tool.search_documentation(
        query=test_query,
        limit=3
    )

    # 結果を表示
    print(f"Found {len(results)} results:")
    for i, result in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"Score: {result.get('score')}")
        print(f"Text snippet: {result.get('text')[:150]}...")
        doc_info = result.get('document', {})
        print(f"Document: {doc_info.get('title', 'Unknown')} ({doc_info.get('id', 'Unknown')})")

    # クリーンアップ
    doc_tool.close()

    return len(results) > 0

if __name__ == "__main__":
    if test_search_functionality():
        print("\n✅ Search functionality working correctly!")
    else:
        print("\n❌ Search functionality test failed!")
```

## MCP との統合テスト

最後に、MCP フレームワークとの統合をテストします：

1. DocumentationGPTTool が登録された MCP サーバーを起動
2. MCP API エンドポイントにテストリクエストを送信：

```bash
curl -X POST http://localhost:8000/api/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "documentation_search",
    "parameters": {
      "query": "How to set up Neo4j",
      "limit": 3
    }
  }'
```

関連するドキュメントを含む適切にフォーマットされた結果が返されることを確認してください。

## トラブルシューティング

テスト中に問題が発生した場合：

1. **接続失敗**: 設定のポート番号を確認（Neo4j: 7687、Qdrant: 6333）
2. **バージョン互換性**: Qdrant クライアントバージョンがサーバーと互換性があることを確認
3. **空の結果**: データベースにドキュメントデータが適切に投入されていることを確認
4. **結果品質が低い**: エンベディングモデルまたは検索パラメータを調整
5. **レスポンスフォーマットのエラー**: 結果エンリッチメントロジックを期待されるフォーマットに合わせて更新

## パフォーマンス指標

テスト中に以下の主要な指標を監視してください：

- **レスポンスタイム**: ほとんどのクエリで1秒未満であること
- **結果の関連性**: 結果の少なくとも70%がクエリに関連していること
- **メモリ使用量**: ツールインスタンスで500MB以下に抑えること
- **エラー率**: リクエストの1%未満が失敗すること
