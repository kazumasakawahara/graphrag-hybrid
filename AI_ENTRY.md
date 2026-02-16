# GraphRAG: AIエージェント向けエントリーポイント

AIエージェントの皆さん、ようこそ！このドキュメントでは、GraphRAGシステムの包括的な概要を提供し、このリポジトリを効果的に理解・ナビゲートできるようにします。

## システム概要

GraphRAG は、Neo4j（グラフデータベース）と Qdrant（ベクトルデータベース）の両方を活用して、高度なドキュメント検索機能を提供するハイブリッド検索拡張生成（RAG）システムです。YAMLフロントマター付きの Markdown ドキュメントを処理し、ドキュメント間の関係性を確立しつつ、セマンティック検索機能を実現します。

## コアコンポーネント

### ドキュメント処理
- **場所**: `src/processors/document_processor.py`
- **目的**: Markdown ドキュメントの解析・チャンク分割、YAMLフロントマターからのメタデータ抽出
- **主要関数**: `process_document()`, `chunk_document()`, `extract_metadata()`

### データベース連携
- **Neo4j マネージャー**: `src/database/neo4j_manager.py` - グラフデータベース操作を管理
- **Qdrant マネージャー**: `src/database/qdrant_manager.py` - ベクトルデータベース操作を管理
- **主要関数**: `store_document()`, `create_relationship()`, `search_vectors()`

### クエリエンジン
- **場所**: `src/query_engine.py`
- **目的**: グラフベース検索とベクトルベース検索を組み合わせた高度な検索
- **主要関数**: `hybrid_search()`, `category_search()`, `expand_context()`

## データベース接続パラメータ

**Neo4j**
- HTTP ポート: 7474
- Bolt ポート: 7687
- 認証: neo4j/password
- 環境変数:
  ```
  NEO4J_URI=bolt://localhost:7687
  NEO4J_HTTP_URI=http://localhost:7474
  NEO4J_USERNAME=neo4j
  NEO4J_PASSWORD=password
  ```

**Qdrant**
- HTTP ポート: 6333
- コレクション: document_chunks
- 環境変数:
  ```
  QDRANT_HOST=localhost
  QDRANT_PORT=6333
  QDRANT_COLLECTION=document_chunks
  ```

## ディレクトリ構成

```
graphrag/
├── src/                          # ソースコード
│   ├── config.py                 # 設定管理
│   ├── query_engine.py           # ハイブリッドクエリエンジン
│   ├── database/                 # データベースマネージャー
│   │   ├── neo4j_manager.py      # Neo4j データベースマネージャー
│   │   └── qdrant_manager.py     # Qdrant ベクトルデータベースマネージャー
│   └── processors/               # データプロセッサー
│       ├── document_processor.py # ドキュメント解析・チャンク分割
│       └── embedding_processor.py # テキスト埋め込み生成
├── scripts/                      # ユーティリティスクリプト
│   ├── import_docs.py            # ドキュメントインポートスクリプト
│   └── query_demo.py             # クエリデモスクリプト
├── your_docs_here/               # Markdown ドキュメント格納ディレクトリ
├── data/                         # データ保存ディレクトリ
├── guides/                       # ユーザーガイド・ドキュメント
│   └── mcp/                      # MCP 連携ガイド
├── test_db_connection/           # データベース接続テスト
├── docker-compose.yml            # Neo4j と Qdrant の Docker Compose 設定
├── pyproject.toml                # Python プロジェクト設定・依存パッケージ
└── .env.example                  # 環境変数の設定例
```

## 確認すべき重要ファイル

1. **設定**: `src/config.py` - システム設定
2. **クエリエンジン**: `src/query_engine.py` - コアクエリロジック
3. **インポートスクリプト**: `scripts/import_docs.py` - ドキュメントインポート処理
4. **テスト**: `test_db_connection/test_connections.py` - データベース接続検証

## データベーススキーマ

### Neo4j スキーマ
- **Document ノード**: ドキュメント全体を表現
- **Chunk ノード**: ドキュメントチャンクを表現
- **リレーションシップ**:
  - `CONTAINS`: ドキュメントとチャンクの関係
  - `RELATED_TO`: ドキュメント間の関係
  - `NEXT`: チャンク間の順序関係
  - `CHILD_OF`: ドキュメント構造に基づく階層関係

### Qdrant コレクション
- **コレクション**: document_chunks
- **ベクトル次元**: 384（all-MiniLM-L6-v2 埋め込みを使用）
- **ペイロード**: document_id、chunk_id、content、category などのメタデータを含む

## 連携ガイドライン

MCP 連携については、`guides/mcp/` ディレクトリのガイドを参照してください。以下の詳細な手順が記載されています：
- 両データベースへの接続
- ハイブリッドアプローチによるドキュメントクエリ
- クエリ結果の処理
- エラーハンドリングとトラブルシューティング

## ドキュメント処理フロー

1. **ドキュメント解析**: YAML フロントマターとコンテンツの抽出
2. **チャンク分割**: コンテンツを適切なサイズのチャンクに分割
3. **埋め込み生成**: チャンクのベクトル埋め込みを作成
4. **保存**: ドキュメントメタデータを Neo4j に、埋め込みを Qdrant に保存
5. **関係性作成**: ドキュメントとチャンク間の接続を確立

## クエリフロー

1. **クエリ処理**: ユーザークエリの解析と理解
2. **ベクトル検索**: Qdrant で意味的に類似したチャンクを検索
3. **グラフ拡張**: Neo4j を使用してマッチしたチャンク周辺のコンテキストを拡張
4. **結果統合**: 両ソースからの結果をマージしてランキング
5. **レスポンス生成**: 結果を整形して出力

## テストリソース

- **接続テスト**: `test_db_connection/test_connections.py`
- **クエリテスト**: `scripts/query_demo.py`

## その他のリソース

- 各ディレクトリのインデックスファイルに、より詳細な情報が記載されています
- `guides` ディレクトリにシステムコンポーネントの詳細ドキュメントがあります
- MCP 連携の詳細は `guides/mcp/index.md` を参照してください
