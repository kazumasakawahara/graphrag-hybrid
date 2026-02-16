# Neo4j と Qdrant データベースセットアップガイド

このガイドでは、GraphRAG MCP サーバーで使用する Neo4j（グラフデータベース）と Qdrant（ベクトルデータベース）のセットアップと設定方法について説明します。

## 目次

- [Neo4j と Qdrant データベースセットアップガイド](#neo4j-と-qdrant-データベースセットアップガイド)
  - [目次](#目次)
  - [概要](#概要)
  - [Docker Compose セットアップ](#docker-compose-セットアップ)
  - [Neo4j セットアップ](#neo4j-セットアップ)
    - [手動インストール](#手動インストール)
    - [設定](#設定)
    - [データベーススキーマ設計](#データベーススキーマ設計)
    - [基本操作](#基本操作)
  - [Qdrant セットアップ](#qdrant-セットアップ)
    - [手動インストール](#手動インストール-1)
    - [設定](#設定-1)
    - [コレクションセットアップ](#コレクションセットアップ)
    - [基本操作](#基本操作-1)
  - [セキュリティに関する考慮事項](#セキュリティに関する考慮事項)
  - [セットアップのテスト](#セットアップのテスト)
  - [トラブルシューティング](#トラブルシューティング)

## 概要

このプロジェクトでは以下を組み合わせたハイブリッドアプローチを使用します：
- **Neo4j**: エンティティ間の構造化された関係を保存するグラフデータベース
- **Qdrant**: セマンティック類似検索のためのベクトルデータベース

両データベースは MCP サーバーが接続する個別のサービスとしてセットアップする必要があります。

## Docker Compose セットアップ

開発用に両データベースをセットアップする最も簡単な方法は Docker Compose を使用することです。`docker-compose.yml` ファイルを作成してください：

```yaml
version: '3'

services:
  neo4j:
    image: neo4j:5.13.0
    container_name: graphrag_neo4j
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_apoc_export_file_enabled=true
      - NEO4J_apoc_import_file_enabled=true
      - NEO4J_apoc_import_file_use__neo4j__config=true
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - neo4j_import:/var/lib/neo4j/import
      - neo4j_plugins:/plugins
    networks:
      - graphrag_network

  qdrant:
    image: qdrant/qdrant:v1.5.1
    container_name: graphrag_qdrant
    ports:
      - "6335:6333"  # HTTP（非標準ポートにマッピング）
      - "6334:6334"  # gRPC
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT_ALLOW_CORS=true
    networks:
      - graphrag_network

volumes:
  neo4j_data:
  neo4j_logs:
  neo4j_import:
  neo4j_plugins:
  qdrant_data:

networks:
  graphrag_network:
    driver: bridge
```

サービスを起動するには：

```bash
docker-compose up -d
```

サービスを停止するには：

```bash
docker-compose down
```

## Neo4j セットアップ

### 手動インストール

Docker を使用しない場合は、Neo4j を直接インストールできます：

1. [公式ウェブサイト](https://neo4j.com/download/)から Neo4j Community Edition をダウンロード
2. お使いの OS の手順に従ってインストール
3. Neo4j サーバーを起動し、初期パスワードを設定
4. ポート 7474（HTTP）と 7687（Bolt）を使用するようにサーバーを設定

### 設定

Neo4j の主要な設定パラメータ：

- **接続 URL**: `bolt://localhost:7687`
- **デフォルト認証情報**: ユーザー名 `neo4j`、パスワード `password`（本番環境では変更してください）
- **Web インターフェース**: 起動後 http://localhost:7474 でアクセス可能

### データベーススキーマ設計

この GraphRAG プロジェクトでは、以下のスキーマを使用します：

```cypher
// ノードラベル
CREATE CONSTRAINT IF NOT EXISTS FOR (c:Content) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE;

// 高速検索用インデックス
CREATE INDEX IF NOT EXISTS FOR (c:Content) ON (c.text);
CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.title);
CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.category);
CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.path);
```

### 基本操作

Cypher シェルまたは Web インターフェースを使用して Neo4j に接続し、以下のコマンドを試してください：

```cypher
// ドキュメントノードを作成
CREATE (d:Document {id: "doc1", title: "GraphRAG Architecture", path: "/docs/architecture.md"})

// ドキュメントのコンテンツチャンクを作成
CREATE (c1:Content {id: "chunk1", text: "This document describes the GraphRAG architecture combining Neo4j and Qdrant."})
CREATE (c2:Content {id: "chunk2", text: "The system uses a hybrid approach with vector similarity and graph relationships."})

// リレーションシップを作成
MATCH (d:Document {id: "doc1"})
MATCH (c1:Content {id: "chunk1"})
MATCH (c2:Content {id: "chunk2"})
CREATE (d)-[:CONTAINS]->(c1)
CREATE (d)-[:CONTAINS]->(c2)
CREATE (c1)-[:NEXT]->(c2)

// 関連コンテンツをクエリ
MATCH (c:Content {id: "chunk1"})-[r:NEXT]->(related)
RETURN c.text AS source, related.text AS related_content
```

## Qdrant セットアップ

### 手動インストール

Docker を使用しない場合：

1. [GitHub](https://github.com/qdrant/qdrant/releases) から最新の Qdrant リリースをダウンロード
2. お使いの OS の手順に従って展開・実行
3. HTTP 用にポート 6333、gRPC 用にポート 6334 を使用するようにサーバーを設定
4. API エンドポイントにアクセスしてインストールを確認

### 設定

Qdrant の主要な設定：

- **HTTP URL**: http://localhost:6333
- **gRPC URL**: http://localhost:6334
- **Web ダッシュボード**: http://localhost:6335/dashboard でアクセス可能

### コレクションセットアップ

適切な設定でドキュメントチャンク用のコレクションを初期化します：

```python
from qdrant_client import QdrantClient
from qdrant_client.http import models
import warnings

# バージョン互換性の警告を抑制
warnings.filterwarnings("ignore", category=UserWarning, module="qdrant_client")

# Qdrant に接続
client = QdrantClient("localhost", port=6333)

# ドキュメントエンベディング用のコレクションを作成
# all-MiniLM-L6-v2 エンベディングに 384 次元を使用
client.create_collection(
    collection_name="document_chunks",
    vectors_config=models.VectorParams(
        size=384,  # エンベディングモデルの次元数
        distance=models.Distance.COSINE
    ),
)

# 効率的なフィルタリング用のペイロードインデックスを作成
client.create_payload_index(
    collection_name="document_chunks",
    field_name="metadata.doc_id",
    field_schema=models.PayloadSchemaType.KEYWORD,
)

# チャンクシーケンス用のペイロードインデックスを作成
client.create_payload_index(
    collection_name="document_chunks",
    field_name="metadata.sequence",
    field_schema=models.PayloadSchemaType.INTEGER,
)
```

### 基本操作

一般的な操作の例：

```python
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
import warnings

# バージョン互換性の警告を抑制
warnings.filterwarnings("ignore", category=UserWarning, module="qdrant_client")

# クライアントを初期化
qdrant = QdrantClient(host="localhost", port=6333)
model = SentenceTransformer('all-MiniLM-L6-v2')

# ドキュメントを挿入
text = "This document describes the GraphRAG architecture."
embedding = model.encode(text).tolist()
qdrant.upsert(
    collection_name="document_chunks",
    points=[
        {
            "id": "chunk1",
            "vector": embedding,
            "payload": {
                "text": text,
                "metadata": {
                    "doc_id": "doc1",
                    "chunk_id": "chunk1",
                    "sequence": 1
                }
            }
        }
    ]
)

# 類似ドキュメントを検索
query = "Tell me about the GraphRAG architecture"
query_vector = model.encode(query).tolist()

# 異なる Qdrant バージョンに対応する互換性のある検索アプローチ
try:
    # 新しい Qdrant バージョン
    search_result = qdrant.search(
        collection_name="document_chunks",
        query_vector=query_vector,
        limit=5
    )
except Exception as e:
    # 互換性の問題に対するフォールバック
    print(f"Using fallback search due to: {str(e)}")
    search_result = qdrant.search(
        collection_name="document_chunks",
        query_vector=query_vector,
        limit=5
    )

for result in search_result:
    print(f"ID: {result.id}, Score: {result.score}")
    print(f"Text: {result.payload['text']}")
    print("---")
```

## セキュリティに関する考慮事項

本番環境向け：

1. **Neo4j**:
   - デフォルト認証情報を変更
   - Bolt 接続の SSL を有効化
   - ロールベースのアクセス制御を設定
   - ネットワーク分離を検討

2. **Qdrant**:
   - 認証用の API キーを設定
   - 本番環境では HTTPS を使用
   - ネットワーク分離を検討
   - 適切なバックアップ戦略を実装

## セットアップのテスト

以下のチェックでセットアップが正しく動作していることを確認してください：

1. **Neo4j**:
   - http://localhost:7474 で Web インターフェースにアクセス
   - 簡単な Cypher クエリを実行: `MATCH (n) RETURN n LIMIT 5`
   - Bolt プロトコルで接続を確認: `bolt://localhost:7687`

2. **Qdrant**:
   - サービスのステータスを確認: http://localhost:6335/dashboard
   - コレクション API を使用: http://localhost:6335/collections

3. **MCP からの接続**:
   - Python ドライバーを使用して Neo4j 接続をテスト
   - Python クライアントを使用して Qdrant 接続をテスト
   - `test_db_connection/test_connections.py` のテストスクリプトで両接続を確認

## トラブルシューティング

よくある問題と解決策：

- **Neo4j が起動しない**: Docker 使用時は `./neo4j_logs` のログを確認
- **Qdrant 接続拒否**: ポートが正しく公開されているか確認（HTTP は 6333、gRPC は 6334）
- **認証エラー**: 設定とコードの両方で認証情報が一致しているか確認
- **Neo4j クエリが遅い**: `EXPLAIN` と `PROFILE` でインデックスの使用状況を確認
- **ベクトル次元の不一致**: エンベディングの次元数が Qdrant コレクションと一致しているか確認（all-MiniLM-L6-v2 の場合は 384）
- **バージョン互換性の問題**: サンプルに示された警告抑制を使用するか、クライアントライブラリをサーバーバージョンに合わせて更新
