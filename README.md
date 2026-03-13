# GraphRAG Hybrid

[![CI](https://github.com/kazumasakawahara/graphrag-hybrid/actions/workflows/ci.yml/badge.svg)](https://github.com/kazumasakawahara/graphrag-hybrid/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Neo4j グラフデータベースと Qdrant ベクトルデータベースを組み合わせたハイブリッド検索拡張生成（RAG）システムです。セマンティック検索、グラフ構造ナビゲーション、エンティティ検索の 3 軸を統合し、高精度なドキュメント検索を実現します。

> **AI エージェントの方へ**: このリポジトリを探索する AI エージェントの方は、まず [AI_ENTRY.md](AI_ENTRY.md) をご覧ください。

## システム概要

```
                          +-------------------+
                          |   Claude Desktop  |
                          |   / AI エージェント |
                          +--------+----------+
                                   |
                              MCP (STDIO)
                                   |
                          +--------v----------+
                          |   FastMCP Server   |
                          |   (server.py)      |
                          |   8 ツール提供      |
                          +--------+----------+
                                   |
                     +-------------+-------------+
                     |                           |
              +------v------+           +--------v--------+
              |  Neo4j 5.x  |           |   Qdrant 1.5+   |
              |  グラフDB    |           |   ベクトルDB     |
              |             |           |                  |
              | Document    |           | document_chunks  |
              | Chunk       |           | 768次元ベクトル   |
              | Entity      |           | (multilingual-   |
              |             |           |  e5-base)        |
              +-------------+           +-----------------+
                     |
              +------v------+
              | Gemini 2.5  |
              | Flash       |
              | エンティティ |
              | 抽出        |
              +-------------+

ハイブリッド検索スコアリング:
  セマンティック 60% + グラフ 20% + エンティティ 20%
```

## 主な機能

- **ハイブリッド検索**: セマンティック (60%) + グラフ (20%) + エンティティ (20%) の重み付けスコアリング
- **多言語対応埋め込み**: intfloat/multilingual-e5-base（768 次元）による日本語・英語対応
- **日本語チャンク分割**: 日本語文境界ベースのチャンキング（デフォルト 800 文字、150 文字オーバーラップ）
- **AI エンティティ抽出**: Gemini 2.5 Flash によるエンティティ・関係性の自動抽出とナレッジグラフ構築
- **PDF 対応**: pymupdf4llm による PDF から Markdown への変換
- **MCP サーバー**: FastMCP による 8 ツール提供で Claude Desktop と直接連携
- **Web UI**: Streamlit によるドキュメント管理・エンティティ閲覧画面
- **設定管理**: Pydantic Settings v2 による型安全な環境変数管理

## クイックスタート

```bash
# 1. リポジトリをクローン
git clone https://github.com/kazumasakawahara/graphrag-hybrid.git
cd graphrag-hybrid

# 2. 依存パッケージをインストール（uv を使用）
uv sync

# 3. 環境変数を設定
cp .env.example .env
# .env を編集して設定を行う（特に NEO4J_URI と GEMINI_API_KEY）

# 4. Neo4j と Qdrant を起動
docker compose up -d

# 5. ドキュメントをインポート
uv run python scripts/import_docs.py --docs-dir ./your_docs_here --recursive

# 6. Web UI を起動
uv run streamlit run app.py
```

## 前提条件

- Python 3.10 以上
- [uv](https://docs.astral.sh/uv/)（Python パッケージマネージャー）
- Docker および Docker Compose
- Gemini API キー（エンティティ抽出を使用する場合。[Google AI Studio](https://aistudio.google.com/) で取得）

## インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/kazumasakawahara/graphrag-hybrid.git
cd graphrag-hybrid
```

### 2. 依存パッケージのインストール

```bash
uv sync
```

### 3. 環境変数の設定

```bash
cp .env.example .env
```

`.env` ファイルを編集し、実際の環境に合わせて設定します。特に以下の項目を確認してください：

- `NEO4J_URI`: docker-compose.yml のポートマッピングに合わせて `bolt://localhost:7689` に変更
- `GEMINI_API_KEY`: エンティティ抽出を使用する場合に設定

### 4. データベースの起動

```bash
docker compose up -d
```

以下のサービスが起動します：

| サービス | ポート（ホスト側） | ポート（コンテナ内） | 用途 |
|---------|-------------------|-------------------|------|
| Neo4j HTTP | 7476 | 7474 | ブラウザ管理画面 |
| Neo4j Bolt | 7689 | 7687 | ドライバー接続 |
| Qdrant HTTP | 6333 | 6333 | REST API |
| Qdrant gRPC | 6334 | 6334 | 高速通信 |

## 使い方

### Web UI（推奨）

Streamlit の管理画面からドキュメントの管理と検索が可能です：

```bash
uv run streamlit run app.py
```

ブラウザで `http://localhost:8501` が開き、以下の操作が可能です：

- PDF / Markdown ファイルのドラッグ&ドロップアップロード
- カテゴリ・タイトルの設定
- 登録済みドキュメントの一覧・削除
- エンティティグラフの閲覧

### CLI

コマンドラインからドキュメントのインポートと検索が可能です：

```bash
# ドキュメントのインポート
uv run python scripts/import_docs.py --docs-dir ./your_docs_here --recursive

# ハイブリッド検索
uv run python scripts/query_demo.py --query "検索クエリ" --type hybrid --limit 5

# カテゴリ検索
uv run python scripts/query_demo.py --query "検索クエリ" --type category --category "カテゴリ名"

# ドキュメント取得
uv run python scripts/query_demo.py --document "doc_id"

# カテゴリ一覧
uv run python scripts/query_demo.py --list-categories

# 統計情報
uv run python scripts/query_demo.py --stats
```

### MCP サーバー

Claude Desktop やその他の MCP 対応クライアントから利用できます：

```bash
# STDIO モード（Claude Desktop 用）
uv run python server.py

# HTTP モード（開発・テスト用）
uv run python server.py --http
```

#### Claude Desktop での設定

`claude_desktop_config.json` に以下を追加します：

```json
{
  "mcpServers": {
    "graphrag": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/graphrag-hybrid", "python", "server.py"],
      "env": {}
    }
  }
}
```

`/path/to/graphrag-hybrid` を実際のプロジェクトパスに置き換えてください。

#### MCP ツール一覧

| ツール名 | 説明 | 主なパラメータ |
|---------|------|--------------|
| `search` | ハイブリッド検索 | `query`, `limit`, `category`, `search_type` |
| `get_document` | ドキュメント取得 | `doc_id` |
| `expand_context` | コンテキスト拡張 | `chunk_id`, `context_size` |
| `get_categories` | カテゴリ一覧取得 | なし |
| `get_statistics` | 統計情報取得 | なし |
| `ingest_document` | ドキュメント取り込み | `file_path` |
| `search_entities` | エンティティ検索 | `query`, `limit` |
| `get_entity_graph` | エンティティグラフ取得 | `entity_name` |

## ドキュメントフォーマット

本システムは YAML フロントマター付きの Markdown ファイルと PDF ファイルを処理します。

### Markdown フォーマット

```markdown
---
title: ドキュメントタイトル            # 必須
category: カテゴリ名                  # 必須
updated: '2024-01-01'                # 任意
related:                             # 任意：関連ドキュメント
  - path/to/related-doc.md
key_concepts:                        # 任意：検索用キーコンセプト
  - concept_1
  - concept_2
---

# ドキュメントタイトル

本文をここに記述します。
```

### 構成のベストプラクティス

- フロントマターの後に `# タイトル`（H1）で始める
- 適切な見出し階層（`##`、`###` など）を使用する
- 言語識別子付きのコードブロックを含める
- `related` フィールドで関連ドキュメントとの関係性を定義する
- `key_concepts` でドキュメントの主要概念を明示する

### PDF ファイル

PDF ファイルは pymupdf4llm により Markdown に変換された後、同様に処理されます。Web UI からのアップロード時にタイトルとカテゴリを指定できます。

## プロジェクト構成

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

## 設定リファレンス

すべての設定は環境変数または `.env` ファイルで管理します。Pydantic Settings v2 により型安全に読み込まれます。

### Neo4j 設定

| 変数名 | デフォルト値 | 説明 |
|--------|------------|------|
| `NEO4J_URI` | `bolt://localhost:7687` | Bolt プロトコル接続 URI |
| `NEO4J_USER` | `neo4j` | 認証ユーザー名 |
| `NEO4J_PASSWORD` | `password` | 認証パスワード |
| `NEO4J_DATABASE` | `neo4j` | 使用するデータベース名 |

### Qdrant 設定

| 変数名 | デフォルト値 | 説明 |
|--------|------------|------|
| `QDRANT_HOST` | `localhost` | ホスト名 |
| `QDRANT_PORT` | `6333` | HTTP ポート |
| `QDRANT_GRPC_PORT` | `6334` | gRPC ポート |
| `QDRANT_COLLECTION` | `document_chunks` | コレクション名 |
| `QDRANT_PREFER_GRPC` | `true` | gRPC 優先使用 |

### 埋め込みモデル設定

| 変数名 | デフォルト値 | 説明 |
|--------|------------|------|
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-base` | 埋め込みモデル名 |
| `EMBEDDING_DIMENSION` | `768` | ベクトル次元数 |
| `EMBEDDING_DEVICE` | `cpu` | 推論デバイス（`cpu` / `cuda`） |
| `EMBEDDING_MAX_LENGTH` | `512` | 最大トークン長 |

### チャンク分割設定

| 変数名 | デフォルト値 | 説明 |
|--------|------------|------|
| `CHUNK_SIZE` | `800` | チャンクサイズ（文字数） |
| `CHUNK_OVERLAP` | `150` | チャンク間のオーバーラップ（文字数） |

### Gemini API 設定

| 変数名 | デフォルト値 | 説明 |
|--------|------------|------|
| `GEMINI_API_KEY` | なし | Gemini API キー（エンティティ抽出用） |

未設定の場合、エンティティ抽出はスキップされ、セマンティック検索とグラフ検索は正常に動作します。

## テスト

```bash
# 全テストを実行
uv run pytest tests/ -v

# カバレッジ付きで実行
uv run pytest tests/ --cov=src --cov-report=term-missing

# 特定のテストファイルを実行
uv run pytest tests/test_config.py -v
```

テストスイートは `tests/` ディレクトリに 100 テストが含まれており、外部データベース接続なしで実行可能です。

## 開発

### CI/CD

GitHub Actions による自動 CI パイプライン（`.github/workflows/ci.yml`）が設定されています：

- **対象ブランチ**: `main`（push / pull request）
- **Python バージョン**: 3.11, 3.12
- **実行内容**: ruff lint、pyright 型チェック、pytest

### リンターと型チェック

```bash
# リント
uv run ruff check src/ tests/

# 型チェック
uv run pyright src/

# フォーマット
uv run ruff format src/ tests/
```

### Docker

アプリケーション単体のコンテナビルドも可能です：

```bash
docker build -t graphrag-hybrid .
```

## アーキテクチャの設計判断

### ハイブリッド検索スコアリング（60/20/20）

セマンティック検索がベースラインの関連性を提供し、グラフ構造とエンティティ情報で文脈的な関連性を補強する構成としました。エンティティ検索により、固有名詞や専門用語による正確なマッチングも実現しています。

### multilingual-e5-base の採用

日本語と英語の両方に対応する多言語埋め込みモデルとして intfloat/multilingual-e5-base（768 次元）を採用しました。E5 モデルは `query:` / `passage:` プレフィックスによる非対称検索に対応しており、検索クエリとドキュメントで異なるエンコーディングを適用できます。

### 日本語文境界チャンキング

日本語テキストの特性に合わせ、句点（。）などの文境界でチャンク分割を行います。英語の空白ベースの分割とは異なり、文の途中で切れることを防ぎます。

### Pydantic Settings v2

型安全な設定管理により、環境変数の読み込み時にバリデーションが行われます。後方互換性のためにドット記法アクセス（`config.get('neo4j.uri')`）もサポートしています。

### Gemini 2.5 Flash によるエンティティ抽出

ドキュメント取り込み時に Gemini 2.5 Flash を使用してエンティティ（人物、組織、概念、法律用語など）と関係性を自動抽出し、Neo4j のナレッジグラフを拡充します。API キー未設定時は自動的にスキップされるため、最小構成での運用も可能です。

## ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。詳細は [LICENSE](LICENSE) ファイルを参照してください。

## 謝辞

- [Neo4j](https://neo4j.com/) - グラフデータベース
- [Qdrant](https://qdrant.tech/) - ベクトル類似度検索エンジン
- [intfloat/multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base) - 多言語埋め込みモデル
- [Google Gemini](https://ai.google.dev/) - エンティティ抽出
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP サーバーフレームワーク
- [Streamlit](https://streamlit.io/) - Web UI フレームワーク
- [pymupdf4llm](https://github.com/pymupdf/pymupdf4llm) - PDF 変換
