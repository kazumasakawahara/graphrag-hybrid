# GraphRAG Hybrid: AI エージェント向けエントリーポイント

AI エージェントの皆さん、ようこそ。このドキュメントでは、GraphRAG Hybrid システムのアーキテクチャ、スキーマ、ツール、設定を正確に記述しています。

## システム概要

GraphRAG Hybrid は、Neo4j（グラフデータベース）と Qdrant（ベクトルデータベース）を組み合わせたハイブリッド RAG システムです。ドキュメントの取り込み、チャンク分割、埋め込み生成、エンティティ抽出、ハイブリッド検索を提供します。

**ハイブリッド検索スコアリング**: セマンティック 60% + グラフ 20% + エンティティ 20%

## 技術スタック

| コンポーネント | 技術 | 備考 |
|--------------|------|------|
| 埋め込みモデル | intfloat/multilingual-e5-base | 768 次元、E5 プレフィックス（query:/passage:）対応 |
| グラフ DB | Neo4j 5.x | Document, Chunk, Entity ノード |
| ベクトル DB | Qdrant 1.5+ | コレクション: document_chunks |
| エンティティ抽出 | Gemini 2.5 Flash | API キー未設定時はスキップ |
| MCP サーバー | FastMCP | STDIO/HTTP、8 ツール |
| 設定管理 | Pydantic Settings v2 | 型安全な環境変数管理 |
| パッケージ管理 | uv | pyproject.toml ベース |
| Web UI | Streamlit | ドキュメント管理・エンティティ閲覧 |
| PDF 変換 | pymupdf4llm | PDF -> Markdown |
| チャンキング | 日本語文境界ベース | 800 文字、150 オーバーラップ |
| Python | >= 3.10 | |

## コアコンポーネント

### 設定管理

- **場所**: `src/config.py`
- **方式**: Pydantic Settings v2（`BaseSettings` ベース）
- **構造**: `Config` -> `Neo4jSettings`, `QdrantSettings`, `EmbeddingSettings`, `ChunkingSettings`
- **アクセス**: `config.neo4j.uri` または `config.get('neo4j.uri')`（後方互換）
- **シングルトン**: モジュールレベルの `config = Config()` で提供

### ドキュメント処理

- **場所**: `src/processors/document_processor.py`
- **機能**: YAML フロントマター解析、日本語文境界ベースのチャンク分割
- **PDF 変換**: `src/processors/pdf_processor.py`（pymupdf4llm 使用）
- **Markdown 処理**: `src/processors/markdown_processor.py`

### 埋め込み生成

- **場所**: `src/processors/embedding_processor.py`
- **モデル**: `intfloat/multilingual-e5-base`（768 次元）
- **特記**: E5 プレフィックス（`query:` / `passage:`）を自動付与

### エンティティ抽出

- **場所**: `src/processors/entity_extractor.py`
- **モデル**: Gemini 2.5 Flash（`google-genai` パッケージ使用）
- **抽出対象**: 人物、組織、概念、法律用語、技術用語など
- **依存**: `GEMINI_API_KEY` 環境変数（未設定時は自動スキップ）

### データベース管理

- **Neo4j**: `src/database/neo4j_manager.py` - グラフ操作、ドキュメント・チャンク・エンティティの CRUD
- **Qdrant**: `src/database/qdrant_manager.py` - ベクトル操作、チャンク埋め込みの保存・検索

### クエリエンジン

- **場所**: `src/query_engine.py`
- **機能**: ハイブリッド検索（セマンティック + グラフ + エンティティ）、カテゴリ検索、コンテキスト拡張
- **スコアリング**: semantic 60% + graph 20% + entity 20%

### MCP ツール実装

- **場所**: `src/graphrag_mcp_tool.py`
- **役割**: クエリエンジンとデータベースマネージャーを統合した高レベル API

## Neo4j スキーマ

### ノード

| ラベル | 主要プロパティ | 一意制約 |
|--------|-------------|---------|
| `Document` | `id`, `title`, `category`, `created_at` | `id` |
| `Chunk` | `id`, `document_id`, `content`, `chunk_index`, `section_title` | `id` |
| `Entity` | `name`, `type`, `description` | `name` |

### リレーションシップ

| 型 | 始点 | 終点 | 説明 |
|----|------|------|------|
| `HAS_CHUNK` | Document | Chunk | ドキュメントがチャンクを含む |
| `NEXT` | Chunk | Chunk | チャンクの順序関係 |
| `RELATED_TO` | Document | Document | ドキュメント間の関連（`related` フロントマターから） |
| `MENTIONS` | Chunk | Entity | チャンク内でエンティティが言及されている |
| `APPEARS_IN` | Entity | Document | エンティティがドキュメント内に出現する |
| `RELATES_TO` | Entity | Entity | エンティティ間の関係性 |

**注意**: `CONTAINS` や `CHILD_OF` は使用していません。ドキュメントとチャンクの関係は `HAS_CHUNK` です。

### Qdrant コレクション

- **コレクション名**: `document_chunks`
- **ベクトル次元**: 768（intfloat/multilingual-e5-base）
- **ペイロード**: `document_id`, `chunk_id`, `content`, `category`, `section_title`, `chunk_index`

## MCP サーバー

### エントリーポイント

- **場所**: `server.py`
- **フレームワーク**: FastMCP
- **起動**: `uv run python server.py`（STDIO）/ `uv run python server.py --http`（HTTP、ポート 8100）

### 提供ツール（8 ツール）

| ツール | シグネチャ | 説明 |
|--------|----------|------|
| `search` | `(query: str, limit: int = 5, category: str? = None, search_type: str = "hybrid")` | ハイブリッド/セマンティック/カテゴリ検索 |
| `get_document` | `(doc_id: str)` | ドキュメント全体を取得 |
| `expand_context` | `(chunk_id: str, context_size: int = 2)` | チャンク前後のコンテキスト拡張 |
| `get_categories` | `()` | 全カテゴリ一覧 |
| `get_statistics` | `()` | Neo4j / Qdrant 統計情報 |
| `ingest_document` | `(file_path: str)` | Markdown ファイルの取り込み |
| `search_entities` | `(query: str, limit: int = 10)` | エンティティ名で部分一致検索 |
| `get_entity_graph` | `(entity_name: str)` | エンティティの関連グラフ取得 |

### MCP リソース

- `graphrag://status` - システムステータス（Neo4j/Qdrant の状態）

## ディレクトリ構成

```
graphrag-hybrid/
├── src/
│   ├── config.py                 # Pydantic Settings v2 設定管理
│   ├── query_engine.py           # ハイブリッドクエリエンジン
│   ├── graphrag_mcp_tool.py      # MCP ツール実装
│   ├── database/
│   │   ├── neo4j_manager.py      # Neo4j グラフDB管理
│   │   └── qdrant_manager.py     # Qdrant ベクトルDB管理
│   ├── processors/
│   │   ├── document_processor.py  # 日本語対応ドキュメント解析・チャンク分割
│   │   ├── embedding_processor.py # E5 多言語埋め込み生成
│   │   ├── entity_extractor.py    # Gemini エンティティ抽出
│   │   ├── markdown_processor.py  # Markdown 処理
│   │   └── pdf_processor.py       # PDF -> Markdown 変換
│   └── utils/
│       ├── neo4j_utils.py
│       ├── qdrant_utils.py
│       └── query_utils.py
├── tests/                        # pytest テストスイート（100 テスト）
├── scripts/
│   ├── import_docs.py            # ドキュメントインポート
│   ├── query_demo.py             # クエリデモ
│   └── verify_db_structure.py    # DB 構造検証
├── guides/                       # ガイドドキュメント
├── your_docs_here/               # ドキュメント格納ディレクトリ
├── server.py                     # FastMCP サーバー（STDIO/HTTP）
├── app.py                        # Streamlit Web UI
├── docker-compose.yml            # Neo4j + Qdrant
├── Dockerfile                    # アプリケーションコンテナ
├── .github/workflows/ci.yml      # CI パイプライン
├── pyproject.toml                # プロジェクト設定（uv）
└── .env.example                  # 環境変数テンプレート
```

## 環境変数

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7689       # docker-compose では 7689 にマッピング
NEO4J_USER=neo4j
NEO4J_PASSWORD=graphrag123            # docker-compose のデフォルト
NEO4J_DATABASE=neo4j

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_COLLECTION=document_chunks
QDRANT_PREFER_GRPC=true

# 埋め込みモデル
EMBEDDING_MODEL=intfloat/multilingual-e5-base
EMBEDDING_DIMENSION=768
EMBEDDING_DEVICE=cpu
EMBEDDING_MAX_LENGTH=512

# チャンク分割
CHUNK_SIZE=800
CHUNK_OVERLAP=150

# Gemini（エンティティ抽出、任意）
GEMINI_API_KEY=your_api_key_here
```

**注意**: `.env.example` のデフォルト値は古い設定が残っている場合があります。上記の値が現在の正しい設定です。

## テスト

```bash
# 全テスト実行
uv run pytest tests/ -v

# カバレッジ付き
uv run pytest tests/ --cov=src --cov-report=term-missing
```

テストは外部データベース接続なしで実行可能です（モック使用）。

## ドキュメント処理フロー

1. **ファイル読み込み**: Markdown / PDF ファイルの読み込み（PDF は pymupdf4llm で Markdown に変換）
2. **メタデータ抽出**: YAML フロントマターから `title`, `category`, `related`, `key_concepts` を抽出
3. **チャンク分割**: 日本語文境界ベースで 800 文字（150 文字オーバーラップ）のチャンクに分割
4. **埋め込み生成**: intfloat/multilingual-e5-base で 768 次元ベクトルを生成（`passage:` プレフィックス付与）
5. **エンティティ抽出**: Gemini 2.5 Flash でエンティティと関係性を抽出（API キー設定時のみ）
6. **Neo4j 保存**: Document, Chunk, Entity ノードと各リレーションシップを作成
7. **Qdrant 保存**: チャンク埋め込みベクトルとメタデータを保存

## クエリフロー

1. **クエリ受信**: ユーザークエリを受け取る
2. **埋め込み生成**: `query:` プレフィックスを付与して E5 でクエリベクトルを生成
3. **セマンティック検索**: Qdrant でコサイン類似度によるベクトル検索
4. **グラフ検索**: Neo4j で関連チャンク・ドキュメントをグラフ走査
5. **エンティティ検索**: Neo4j でエンティティマッチング
6. **スコア統合**: semantic 60% + graph 20% + entity 20% で重み付け
7. **結果返却**: 統合スコアでランキングした結果を返却

## 重要ファイル（調査の優先順位）

1. `src/config.py` - 全設定の定義（Pydantic Settings v2）
2. `src/query_engine.py` - ハイブリッド検索のコアロジック
3. `server.py` - MCP サーバーのエントリーポイントとツール定義
4. `src/graphrag_mcp_tool.py` - ツールの実装詳細
5. `src/database/neo4j_manager.py` - Neo4j スキーマとクエリ
6. `src/database/qdrant_manager.py` - Qdrant 操作
7. `src/processors/document_processor.py` - チャンク分割ロジック
8. `src/processors/entity_extractor.py` - Gemini エンティティ抽出
