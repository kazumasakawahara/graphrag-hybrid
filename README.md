# GraphRAG: Neo4j と Qdrant のハイブリッド検索システム

Neo4j グラフデータベースと Qdrant ベクトルデータベースを組み合わせた、高度なドキュメント検索を実現する検索拡張生成（RAG）システムです。ドキュメントの関係性とベクトル類似度の両方を活用したハイブリッドアプローチにより、強力な検索機能を提供します。

> **AIエージェントの方へ**: このリポジトリを探索するAIエージェントの方は、まず [AI_ENTRY.md](AI_ENTRY.md) をご覧ください。

## システム概要

GraphRAG は2つの補完的なデータベースを使用します：

1. **Neo4j グラフデータベース**: ドキュメントの関係性、カテゴリ、メタデータを保存
2. **Qdrant ベクトルデータベース**: セマンティック検索のためのドキュメントチャンク埋め込みを保存

## 検証済みデータベース接続情報

| データベース | サービス | ポート | 認証 |
|-------------|---------|--------|------|
| Neo4j       | HTTP    | 7474   | neo4j/password |
| Neo4j       | Bolt    | 7687   | neo4j/password |
| Qdrant      | HTTP    | 6333   | なし（デフォルト） |

### 接続パラメータ

アプリケーションでの使用：

```
# Neo4j 設定
NEO4J_HTTP_URI=http://localhost:7474
NEO4J_BOLT_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Qdrant 設定
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=document_chunks
```

## 機能

- **ドキュメント処理**: YAML フロントマター付きの Markdown ドキュメントの解析とチャンク分割
- **セマンティック検索**: トランスフォーマーモデルを使用したベクトルベースの類似度検索
- **グラフベースナビゲーション**: Neo4j グラフデータベースを使用したドキュメント関係の探索
- **ハイブリッド検索**: セマンティック検索とグラフベースアプローチの組み合わせによる高精度な結果
- **外部連携**: 外部システムとの統合に対応したツール

## プロジェクト構成

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
├── test_db_connection/           # データベース接続テスト
├── docker-compose.yml            # Neo4j と Qdrant の Docker Compose 設定
├── pyproject.toml                # Python プロジェクト設定・依存パッケージ
└── .env.example                  # 環境変数の設定例
```

## セットアップ

### 前提条件

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (Python パッケージマネージャー)
- Docker および Docker Compose
- Neo4j 5.x
- Qdrant 1.5.0+

### インストール

1. リポジトリをクローン：

```bash
git clone https://github.com/yourusername/graphrag.git
cd graphrag
```

2. 依存パッケージをインストール：

```bash
uv sync
```

4. 設定ファイルを作成：

```bash
cp .env.example .env
# .env を編集して設定を行う
```

5. Docker で Neo4j と Qdrant を起動：

```bash
docker-compose up -d
```

### ドキュメントのインポート

#### Web UI（推奨）

Streamlit の管理画面から PDF や Markdown ファイルをアップロードできます：

```bash
uv run streamlit run app.py
```

ブラウザで `http://localhost:8501` が開き、以下の操作が可能です：

- PDF / Markdown ファイルのドラッグ&ドロップアップロード
- カテゴリ・タイトルの設定
- 登録済みドキュメントの一覧・削除

#### CLI

コマンドラインからまとめてインポートすることも可能です：

```bash
uv run python scripts/import_docs.py --docs-dir ./your_docs_here --recursive
```

この処理では以下が行われます：
- ディレクトリ内のすべての Markdown ファイルを処理
- YAML フロントマターからメタデータを抽出
- ドキュメントを適切なサイズにチャンク分割
- ドキュメントのメタデータと関係性を Neo4j に保存
- 埋め込みを生成して Qdrant に保存

## 使い方

### クエリの実行

クエリデモスクリプトを使用してシステムを試す：

```bash
# ハイブリッド検索
python scripts/query_demo.py --query "What is GraphRAG?" --type hybrid --limit 5

# カテゴリ検索
python scripts/query_demo.py --query "documentation" --type category --category "user-guide"

# ドキュメントIDで取得
python scripts/query_demo.py --document "doc_123456"

# 全カテゴリ一覧
python scripts/query_demo.py --list-categories

# システム統計情報の表示
python scripts/query_demo.py --stats
```

### 外部システムとの連携

外部システムとの連携には、`src` ディレクトリ内の Python モジュールを使用してください。詳細な連携手順は `guides/mcp` ディレクトリのガイドを参照してください。

## ドキュメントフォーマット要件

本システムは YAML フロントマター付きの Markdown ファイルを処理します。最適な結果を得るには、以下のフォーマットに従ってください：

### 必須フロントマターフォーマット

```markdown
---
title: アナリティクスとモニタリング            # ドキュメントタイトル（必須）
category: frontend/ux                        # カテゴリパス（必須）
updated: '2023-04-01'                        # 最終更新日（任意）
related:                                     # 関連ドキュメント（任意）
- ui/DATA_FETCHING.md
- ui/STATE_MANAGEMENT.md
- ux/USER_FLOWS.md
key_concepts:                                # インデックス用キーコンセプト（任意）
- analytics_integration
- user_behavior_tracking
- performance_monitoring
---

# アナリティクスとモニタリング

このドキュメントでは、アプリケーション内のアナリティクスとモニタリングのアプローチを説明します。

## アナリティクス戦略

### 基本原則

アナリティクスの実装は以下の原則に従います：

- **目的指向**: ビジネスまたはUXの具体的な質問に紐づいた収集
- **プライバシーファースト**: 明確なユーザー同意のもとでの最小限のデータ収集

## パフォーマンスモニタリング

コードサンプルでは言語識別子を使用します：

```javascript
function trackEvent(eventName, properties) {
  analytics.track(eventName, {
    timestamp: new Date().toISOString(),
    ...properties
  });
}
```
```

### ドキュメント構成のベストプラクティス

- フロントマターの後に単一の `# タイトル`（H1）見出しで始める
- 適切な見出し階層（`##`、`###` など）を使用する
- 言語識別子付きのコードブロックを含める
- リスト、テーブルなどの Markdown 機能を必要に応じて使用する
- 関連ドキュメントへのリンクを適切に配置する
- 検索に重要なキーコンセプトを含める

システムは以下の手順でドキュメントを処理します：
1. フロントマターのメタデータを解析
2. 見出しから階層構造を抽出
3. コンテンツを適切なチャンクに分割
4. 「related」フィールドに基づく関係性を作成
5. 検索精度向上のためキーコンセプトをインデックス化

## 設定

環境変数または `.env` ファイルでシステムを設定します：

- **Neo4j 設定**:
  - `NEO4J_URI=bolt://localhost:7687`
  - `NEO4J_HTTP_URI=http://localhost:7474`
  - `NEO4J_USERNAME=neo4j`
  - `NEO4J_PASSWORD=password`

- **Qdrant 設定**:
  - `QDRANT_HOST=localhost`
  - `QDRANT_PORT=6333`
  - `QDRANT_COLLECTION=document_chunks`

- **埋め込み設定**: テキスト埋め込みのモデル設定
- **チャンク設定**: ドキュメントチャンク分割パラメータ

## 検証

セットアップ後、データベース接続を確認します：

```bash
python test_db_connection/test_connections.py
```

## ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。詳細は [LICENSE](LICENSE) ファイルを参照してください。

## 謝辞

- [Neo4j](https://neo4j.com/) - グラフデータベース
- [Qdrant](https://qdrant.tech/) - ベクトル類似度検索
- [HuggingFace](https://huggingface.co/) - トランスフォーマーモデル
