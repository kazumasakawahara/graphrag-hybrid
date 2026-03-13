# GraphRAG MCP サーバーガイド

GraphRAG Hybrid の MCP（Model Context Protocol）サーバーは、Neo4j グラフデータベースと Qdrant ベクトルデータベースを組み合わせたハイブリッド検索機能を、Claude Desktop や Cursor などの AI ツールに提供します。

## 概要

MCP サーバーは `server.py` で実装されており、FastMCP フレームワークを使用して 8 つのツールを公開します。内部では `GraphRAGMCPTool`（`src/graphrag_mcp_tool.py`）をシングルトンとして初期化し、Neo4j・Qdrant・埋め込みモデルへの接続を管理します。

主な特徴:

- 日本語・英語の両方に対応（multilingual-e5-base モデル使用）
- セマンティック検索、カテゴリ検索、ハイブリッド検索の 3 モード
- ドキュメント取り込み（Markdown ファイル）
- エンティティ検索とナレッジグラフ探索
- E5 モデルの query/passage プレフィックスを自動付与

## 起動方法

### STDIO モード（Claude Desktop / Cursor 用）

```bash
uv run python server.py
```

標準入出力を介して MCP プロトコルで通信します。Claude Desktop や Cursor から自動起動されるため、通常は手動実行不要です。

### HTTP モード（開発・テスト用）

```bash
uv run python server.py --http
```

`http://0.0.0.0:8100` で HTTP サーバーが起動します。ブラウザや curl でツールの動作を確認できます。

## Claude Desktop 設定

`claude_desktop_config.json` に以下を追加してください。

macOS の場合: `~/Library/Application Support/Claude/claude_desktop_config.json`

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

`/path/to/graphrag-hybrid` はプロジェクトのフルパスに置き換えてください。`.env` ファイルがプロジェクトルートに存在すれば、サーバー起動時に自動的に読み込まれます。

## Cursor IDE 設定

Cursor の Settings から MCP サーバーを追加します。

1. Settings を開く（`Cmd+,`）
2. 「MCP」で検索し、MCP Servers セクションを開く
3. 以下の設定を追加:

```json
{
  "graphrag": {
    "command": "uv",
    "args": ["run", "--directory", "/path/to/graphrag-hybrid", "python", "server.py"]
  }
}
```

## ツールリファレンス

### search

ドキュメントをハイブリッド検索します。

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|------|------|-----------|------|
| query | string | はい | - | 検索クエリテキスト |
| limit | int | いいえ | 5 | 返す結果の最大数 |
| category | string | いいえ | null | カテゴリでフィルタ |
| search_type | string | いいえ | "hybrid" | "hybrid", "semantic", "category" |

### get_document

ドキュメント ID を指定して完全なドキュメント情報を取得します。

| パラメータ | 型 | 必須 | 説明 |
|-----------|------|------|------|
| doc_id | string | はい | ドキュメント ID |

### expand_context

特定チャンクの前後のコンテキストを拡張取得します。

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|------|------|-----------|------|
| chunk_id | string | はい | - | チャンク ID |
| context_size | int | いいえ | 2 | 前後に取得するチャンク数 |

### get_categories

登録されている全ドキュメントカテゴリの一覧を取得します。パラメータなし。

### get_statistics

Neo4j と Qdrant 両方のデータベースの統計情報を取得します。パラメータなし。

### ingest_document

Markdown ファイルを読み込み、日本語対応のチャンク分割を行い、Neo4j と Qdrant に登録します。

| パラメータ | 型 | 必須 | 説明 |
|-----------|------|------|------|
| file_path | string | はい | 取り込む Markdown ファイルのパス |

### search_entities

ドキュメントから抽出されたエンティティ（人物、組織、概念など）を名前で検索します。

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|------|------|-----------|------|
| query | string | はい | - | エンティティ名（部分一致） |
| limit | int | いいえ | 10 | 返す結果の最大数 |

### get_entity_graph

指定されたエンティティの関連グラフ（関連エンティティ、出現ドキュメント）を取得します。

| パラメータ | 型 | 必須 | 説明 |
|-----------|------|------|------|
| entity_name | string | はい | エンティティ名（完全一致） |

## 使い方の例

### 基本的な検索フロー

1. **カテゴリを確認**: `get_categories` でどのようなドキュメントが登録されているか把握する
2. **検索**: `search` でクエリを実行する
3. **詳細を確認**: 気になるチャンクがあれば `expand_context` で前後の文脈を取得する
4. **ドキュメント全体を読む**: 必要に応じて `get_document` で全文を取得する

### エンティティ探索フロー

1. **エンティティを検索**: `search_entities` で関連するエンティティを見つける
2. **関係を探索**: `get_entity_graph` でエンティティ間の関係を可視化する
3. **関連ドキュメントを検索**: エンティティが出現するドキュメントから `search` で深掘りする

### ドキュメント追加フロー

1. **ドキュメントを取り込み**: `ingest_document` で Markdown ファイルを登録する
2. **確認**: `get_statistics` でドキュメント数やチャンク数が増加したことを確認する
3. **検索テスト**: `search` で追加したドキュメントが検索できることを確認する

## リソース

MCP サーバーは以下のリソースも公開しています。

| URI | 説明 |
|-----|------|
| `graphrag://status` | Neo4j・Qdrant の接続状態と統計情報 |

## トラブルシューティング

### サーバーが起動しない

- `.env` ファイルがプロジェクトルートに存在するか確認
- `docker compose up -d` で Neo4j と Qdrant が起動しているか確認
- `uv sync` で依存パッケージがインストールされているか確認

### 検索結果が返らない

- `get_statistics` でドキュメントが登録されているか確認
- Qdrant コレクション名が `document_chunks` であるか確認
- 埋め込みモデルがデータ登録時と同一であるか確認

### 接続エラー

- Neo4j Bolt ポート: 7689（docker-compose で 7689:7687 にマッピング）
- Qdrant HTTP ポート: 6333、gRPC ポート: 6334
- 接続パラメータの詳細は [接続ガイド](connection.md) を参照
