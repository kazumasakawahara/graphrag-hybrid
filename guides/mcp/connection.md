# GraphRAG データベース接続ガイド

GraphRAG システムが使用する Neo4j・Qdrant・埋め込みモデルの接続設定を説明します。

## 接続パラメータ

docker-compose.yml でホストポートがマッピングされています。

| サービス | プロトコル | ホストポート | コンテナポート | 用途 |
|---------|----------|------------|-------------|------|
| Neo4j | Bolt | 7689 | 7687 | ドライバー接続 |
| Neo4j | HTTP | 7476 | 7474 | ブラウザ UI |
| Qdrant | HTTP | 6333 | 6333 | REST API |
| Qdrant | gRPC | 6334 | 6334 | 高速通信 |

Neo4j ブラウザには `http://localhost:7476` でアクセスできます。

## 環境変数

すべての接続パラメータは環境変数で設定します。Pydantic Settings により `.env` ファイルから自動読み込みされます。

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7689
NEO4J_USER=neo4j
NEO4J_PASSWORD=graphrag123
NEO4J_DATABASE=neo4j

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_PREFER_GRPC=true
QDRANT_COLLECTION=document_chunks
```

設定クラスの構造（`src/config.py`）:

```python
from src.config import Config

config = Config()
config.neo4j.uri       # "bolt://localhost:7689"
config.qdrant.host     # "localhost"
config.embedding.model_name  # "intfloat/multilingual-e5-base"
config.chunking.chunk_size   # 800
```

## 埋め込みモデル

| 項目 | 値 |
|------|------|
| モデル | `intfloat/multilingual-e5-base` |
| 次元数 | 768 |
| 最大長 | 512 トークン |
| デバイス | cpu（デフォルト） |

### E5 プレフィックス

E5 モデルは入力テキストにプレフィックスが必要です。GraphRAG システムはこれを自動的に付与します。

- **検索クエリ**: `"query: "` + テキスト
- **ドキュメントチャンク（格納時）**: `"passage: "` + テキスト

外部ツールから Qdrant を直接クエリする場合は、クエリベクトル生成時に `"query: "` プレフィックスを付けてからエンコードしてください。

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("intfloat/multilingual-e5-base")
query_vector = model.encode("query: 相続の手続きについて教えて")
```

## チャンキング設定

| 項目 | デフォルト値 |
|------|-----------|
| チャンクサイズ | 800 文字 |
| オーバーラップ | 150 文字 |

日本語文境界（句点「。」）を考慮した分割を行います。環境変数 `CHUNK_SIZE` と `CHUNK_OVERLAP` で変更可能です。

## 接続テスト

### Neo4j

```bash
# Neo4j ブラウザで接続確認
open http://localhost:7476

# Python から確認
uv run python -c "
from neo4j import GraphDatabase
d = GraphDatabase.driver('bolt://localhost:7689', auth=('neo4j', 'graphrag123'))
with d.session() as s:
    print(s.run('MATCH (n) RETURN count(n) AS c').single()['c'], 'nodes')
d.close()
"
```

### Qdrant

```bash
# REST API で確認
curl http://localhost:6333/collections/document_chunks

# ダッシュボード
open http://localhost:6333/dashboard
```

## トラブルシューティング

| 症状 | 確認事項 |
|------|---------|
| Neo4j 接続拒否 | `docker compose ps` で neo4j コンテナが Running か確認。ポートは 7689（7687 ではない） |
| Qdrant 接続拒否 | Qdrant コンテナが起動しているか確認。ポートは 6333 |
| 認証エラー | `.env` の `NEO4J_PASSWORD` が docker-compose.yml の `NEO4J_AUTH` と一致しているか確認 |
| ベクトル次元不一致 | `EMBEDDING_DIMENSION=768` であること。古い 384 次元データが残っている場合はコレクション再作成が必要 |
