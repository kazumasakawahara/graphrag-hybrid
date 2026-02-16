# データベース接続情報

## Neo4j 接続情報

- **ユーザー名**: neo4j
- **パスワード**: password
- **HTTP ポート**: 7474（ブラウザインターフェース）
- **Bolt ポート**: 7687（アプリケーション接続）
- **データベース**: neo4j（デフォルト）

Neo4j ブラウザにアクセスするには：
- Web ブラウザで http://localhost:7474 を開く
- neo4j/password でログイン

## Qdrant 接続情報

- **ホスト**: localhost
- **HTTP ポート**: 6333（REST API）
- **gRPC ポート**: 6334
- **コレクション名**: document_chunks

## 環境変数

`.env` ファイルに以下を追加してください：

```
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=document_chunks
```

## 接続テスト

`test_connections.py` スクリプトにより、両データベースがアクセス可能で正常に動作していることを検証できます。問題が発生した場合は、メインドキュメントのトラブルシューティングセクションを参照してください。

## 検証済み接続情報

接続テストスクリプトにより、以下の接続情報が確認されています：

### Neo4j データベース
- **HTTP ポート**: 7474（ブラウザインターフェース）
- **Bolt ポート**: 7687（アプリケーション接続）
- **認証**: neo4j/password
- **ステータス**: 接続成功 ✅
- **データベース内容**:
  - 162 Document ノード
  - 2785 Content ノード
  - 3652 ノード合計

### Qdrant ベクトルデータベース
- **HTTP ポート**: 6333（REST API）
- **コレクション**: document_chunks
- **ベクトル数**: 2785 ベクトル
- **ベクトル次元**: 384
- **ステータス**: 接続成功 ✅

## MCP 用接続設定

MCP サーバーの `.env` ファイルに以下を追加してください：

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
QDRANT_HOST=localhost
QDRANT_PORT=6333
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
```

## 実装上の注意

Qdrant クライアントバージョン（1.13.3）が Qdrant サーバーバージョン（1.5.1）より新しいため、一部の API 機能で互換性の問題が発生する可能性があります。テストでは接続と基本的な検索に成功しましたが、高度な機能を使用する場合はコードの調整が必要になる可能性があります。

## 次のステップ

1. これらの検証済み接続情報で MCP サーバー設定を更新
2. 基本的なクエリ機能をテスト
3. バージョン互換性の問題に対するエラーハンドリングを実装
