# GraphRAG データベース接続ガイド

このガイドでは、GraphRAG システムで使用する Neo4j グラフデータベースと Qdrant ベクトルデータベースへの接続確立方法を詳しく説明します。

## 検証済み接続パラメータ

広範なテストにより、以下の接続パラメータが確認されています：

| データベース | サービス | ポート | 認証 |
|----------|---------|------|---------------|
| Neo4j    | HTTP    | 7474 | neo4j/password |
| Neo4j    | Bolt    | 7687 | neo4j/password |
| Qdrant   | HTTP    | 6333 | なし（デフォルト） |

> **注意**: 両データベースは標準のデフォルトポートで設定されています。Neo4j は HTTP に 7474、Bolt に 7687 を使用し、Qdrant は HTTP に 6333 を使用します。

## 必要な依存パッケージ

データベースに接続するために以下の Python パッケージをインストールしてください：

```bash
uv add neo4j==5.9.0 qdrant-client==1.6.0 sentence-transformers==2.2.2
```

## Neo4j 接続セットアップ

### 接続文字列のフォーマット

Neo4j の接続文字列は以下のフォーマットに従います：
```bolt://[ホスト名]:[ポート]
```

### 基本的な接続例

```python
from neo4j import GraphDatabase

# 接続パラメータ
neo4j_uri = "bolt://localhost:7688"  # 非標準ポートに注意
neo4j_user = "neo4j"
neo4j_password = "password"

# 接続を確立
driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

# 接続テスト
def test_connection():
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) AS node_count")
        return result.single()["node_count"]

# ノード数を表示
print(f"Connected to Neo4j database with {test_connection()} nodes")

# 完了時に接続を閉じる
driver.close()
```

### エラーハンドリング付き接続

```python
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

def connect_to_neo4j(uri, user, password, max_retries=3):
    """リトライロジックとエラーハンドリング付きで Neo4j に接続"""
    retry_count = 0

    while retry_count < max_retries:
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))

            # 接続を検証
            with driver.session() as session:
                result = session.run("RETURN 1 AS test")
                result.single()

            print(f"✅ Successfully connected to Neo4j at {uri}")
            return driver

        except ServiceUnavailable as e:
            retry_count += 1
            wait_time = 2 ** retry_count  # 指数バックオフ
            print(f"❌ Neo4j connection failed (attempt {retry_count}/{max_retries}): {e}")
            print(f"   Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

        except AuthError as e:
            print(f"❌ Neo4j authentication failed: {e}")
            print("   Please check username and password.")
            break

        except Exception as e:
            print(f"❌ Unexpected error connecting to Neo4j: {e}")
            break

    if retry_count >= max_retries:
        print(f"❌ Failed to connect to Neo4j after {max_retries} attempts")

    return None
```

### 複数ポートのテスト

Neo4j が使用しているポートが不明な場合、複数のポートをテストできます：

```python
def find_neo4j_port(host="localhost", ports=[7687, 7688, 7689]):
    """異なるポートで Neo4j への接続を試行"""
    for port in ports:
        uri = f"bolt://{host}:{port}"
        try:
            with GraphDatabase.driver(uri, auth=("neo4j", "password")) as driver:
                with driver.session() as session:
                    session.run("RETURN 1").single()
                    print(f"✅ Neo4j found on port {port}")
                    return port
        except Exception as e:
            print(f"❌ Neo4j not available on port {port}: {e}")

    print("❌ Could not connect to Neo4j on any of the specified ports")
    return None
```

## Qdrant 接続セットアップ

### 基本的な接続

```python
from qdrant_client import QdrantClient

# 接続パラメータ
qdrant_host = "localhost"
qdrant_port = 6335  # 非標準ポートに注意
qdrant_collection = "document_chunks"

# Qdrant に接続
client = QdrantClient(host=qdrant_host, port=qdrant_port)

# 接続テスト
def test_collection():
    try:
        collection_info = client.get_collection(qdrant_collection)

        # 異なる API バージョンに対応
        vectors_count = None
        if hasattr(collection_info, 'vectors_count'):
            vectors_count = collection_info.vectors_count
        elif hasattr(collection_info, 'points_count'):
            vectors_count = collection_info.points_count

        return vectors_count
    except Exception as e:
        print(f"Error getting collection info: {e}")
        return None

# コレクションサイズを表示
vector_count = test_collection()
if vector_count is not None:
    print(f"Connected to Qdrant collection '{qdrant_collection}' with {vector_count} vectors")
```

### バージョン互換性対応の接続

Qdrant クライアントのバージョンによって API メソッドが異なる場合があります。異なるバージョンに対応する方法：

```python
import warnings
from qdrant_client import QdrantClient

# バージョン互換性の警告を抑制
warnings.filterwarnings("ignore", category=UserWarning, module="qdrant_client")

def connect_to_qdrant(host, port, collection_name, max_retries=3):
    """エラーハンドリングとバージョン互換性対応付きで Qdrant に接続"""
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Qdrant に接続
            client = QdrantClient(host=host, port=port)

            # コレクションを確認して接続を検証
            collection_info = client.get_collection(collection_name)

            # 異なる API バージョンでベクトル数を取得
            vectors_count = None

            # 新しいバージョン向けのアプローチ
            if hasattr(collection_info, 'vectors_count'):
                vectors_count = collection_info.vectors_count
            # 他のバージョン向けのアプローチ
            elif hasattr(collection_info, 'points_count'):
                vectors_count = collection_info.points_count
            # ネストされた構造を探索
            else:
                try:
                    if hasattr(collection_info.config, 'params'):
                        if hasattr(collection_info.config.params, 'vectors'):
                            vectors_count = collection_info.config.params.vectors.size
                except:
                    pass

            if vectors_count is not None:
                print(f"✅ Connected to Qdrant collection '{collection_name}' with {vectors_count} vectors")
            else:
                print(f"✅ Connected to Qdrant collection '{collection_name}', but couldn't determine vector count")

            return client

        except ConnectionError as e:
            retry_count += 1
            wait_time = 2 ** retry_count  # 指数バックオフ
            print(f"❌ Qdrant connection failed (attempt {retry_count}/{max_retries}): {e}")
            print(f"   Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

        except Exception as e:
            print(f"❌ Error connecting to Qdrant: {e}")
            break

    if retry_count >= max_retries:
        print(f"❌ Failed to connect to Qdrant after {max_retries} attempts")

    return None
```

### 複数ポートのテスト

Neo4j と同様に、Qdrant でも複数のポートをテストできます：

```python
def find_qdrant_port(host="localhost", ports=[6333, 6334, 6335]):
    """異なるポートで Qdrant への接続を試行"""
    for port in ports:
        try:
            client = QdrantClient(host=host, port=port)
            collections = client.get_collections().collections
            print(f"✅ Qdrant found on port {port} with {len(collections)} collections")
            return port
        except Exception as e:
            print(f"❌ Qdrant not available on port {port}: {e}")

    print("❌ Could not connect to Qdrant on any of the specified ports")
    return None
```

## エンベディングモデルのセットアップ

ベクトルデータベースを効果的にクエリするには、ベクトルエンベディングの作成に使用したものと同じエンベディングモデルを使用する必要があります：

```python
from sentence_transformers import SentenceTransformer

def load_embedding_model(model_name="all-MiniLM-L6-v2"):
    """エンベディング作成用の Sentence Transformer モデルを読み込み"""
    try:
        model = SentenceTransformer(model_name)
        print(f"✅ Loaded embedding model: {model_name}")
        return model
    except Exception as e:
        print(f"❌ Error loading embedding model: {e}")
        return None

# モデルを読み込み
model = load_embedding_model()

# クエリ用のエンベディングを生成
def generate_embedding(text, model):
    if model is None:
        return None

    try:
        embedding = model.encode(text)
        return embedding
    except Exception as e:
        print(f"❌ Error generating embedding: {e}")
        return None
```

## 完全な接続マネージャーの例

両データベースへの接続を管理する完全な接続マネージャーの例：

```python
import os
import time
import warnings
from typing import Dict, List, Optional, Any, Union

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Qdrant バージョン警告を抑制
warnings.filterwarnings("ignore", category=UserWarning, module="qdrant_client")

class GraphRAGConnectionManager:
    """Neo4j と Qdrant データベースへの接続マネージャー"""

    def __init__(self):
        # Neo4j 接続パラメータ
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        self.neo4j_driver = None

        # Qdrant 接続パラメータ
        self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", "6335"))
        self.qdrant_collection = os.getenv("QDRANT_COLLECTION", "document_chunks")
        self.qdrant_client = None

        # エンベディングモデル
        self.model_name = "all-MiniLM-L6-v2"
        self.model = None

    def connect(self, max_retries=3):
        """両データベースに接続し、エンベディングモデルを読み込み"""
        success = True

        # Neo4j に接続
        if not self._connect_neo4j(max_retries):
            success = False

        # Qdrant に接続
        if not self._connect_qdrant(max_retries):
            success = False

        # エンベディングモデルを読み込み
        if not self._load_model():
            success = False

        return success

    def _connect_neo4j(self, max_retries=3):
        """リトライロジック付きで Neo4j に接続"""
        retry_count = 0

        while retry_count < max_retries:
            try:
                self.neo4j_driver = GraphDatabase.driver(
                    self.neo4j_uri,
                    auth=(self.neo4j_user, self.neo4j_password)
                )

                # 接続を検証
                with self.neo4j_driver.session() as session:
                    result = session.run("MATCH (d:Document) RETURN count(d) AS count")
                    record = result.single()
                    print(f"✅ Connected to Neo4j with {record['count']} documents")

                return True

            except ServiceUnavailable as e:
                retry_count += 1
                wait_time = 2 ** retry_count  # 指数バックオフ
                print(f"❌ Neo4j connection failed (attempt {retry_count}/{max_retries}): {e}")
                print(f"   Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

            except AuthError as e:
                print(f"❌ Neo4j authentication failed: {e}")
                print("   Please check username and password.")
                break

            except Exception as e:
                print(f"❌ Unexpected error connecting to Neo4j: {e}")
                break

        if retry_count >= max_retries:
            print(f"❌ Failed to connect to Neo4j after {max_retries} attempts")

        return False

    def _connect_qdrant(self, max_retries=3):
        """リトライロジック付きで Qdrant に接続"""
        retry_count = 0

        while retry_count < max_retries:
            try:
                self.qdrant_client = QdrantClient(
                    host=self.qdrant_host,
                    port=self.qdrant_port
                )

                # 接続を検証
                collection_info = self.qdrant_client.get_collection(self.qdrant_collection)

                # 異なる API バージョンでベクトル数を取得
                vectors_count = None

                # 新しいバージョン向けのアプローチ
                if hasattr(collection_info, 'vectors_count'):
                    vectors_count = collection_info.vectors_count
                # 他のバージョン向けのアプローチ
                elif hasattr(collection_info, 'points_count'):
                    vectors_count = collection_info.points_count
                # ネストされた構造を探索
                else:
                    try:
                        if hasattr(collection_info.config, 'params'):
                            if hasattr(collection_info.config.params, 'vectors'):
                                vectors_count = collection_info.config.params.vectors.size
                    except:
                        pass

                if vectors_count is not None:
                    print(f"✅ Connected to Qdrant collection '{self.qdrant_collection}' with {vectors_count} vectors")
                else:
                    print(f"✅ Connected to Qdrant collection '{self.qdrant_collection}', but couldn't determine vector count")

                return True

            except ConnectionError as e:
                retry_count += 1
                wait_time = 2 ** retry_count  # 指数バックオフ
                print(f"❌ Qdrant connection failed (attempt {retry_count}/{max_retries}): {e}")
                print(f"   Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

            except Exception as e:
                print(f"❌ Error connecting to Qdrant: {e}")
                break

        if retry_count >= max_retries:
            print(f"❌ Failed to connect to Qdrant after {max_retries} attempts")

        return False

    def _load_model(self):
        """Sentence Transformer モデルを読み込み"""
        try:
            self.model = SentenceTransformer(self.model_name)
            print(f"✅ Loaded embedding model: {self.model_name}")
            return True
        except Exception as e:
            print(f"❌ Error loading embedding model: {e}")
            return False

    def close(self):
        """すべての接続を閉じる"""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            print("✅ Neo4j connection closed")

        # Qdrant クライアントは明示的な終了が不要

        print("✅ All connections closed")
```

## 使用例

接続マネージャーの使用方法：

```python
# 接続マネージャーを作成
manager = GraphRAGConnectionManager()

# データベースに接続
if manager.connect():
    print("All connections established successfully")

    # 接続を使用...

    # 完了時に接続を閉じる
    manager.close()
else:
    print("Failed to establish all connections")
```

## 環境変数

設定を簡素化するために、接続パラメータに環境変数を使用することを検討してください：

```bash
# .env ファイル
NEO4J_URI=bolt://localhost:7688
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
QDRANT_HOST=localhost
QDRANT_PORT=6335
QDRANT_COLLECTION=document_chunks
```

Python で環境変数を読み込むには：

```python
import os
from dotenv import load_dotenv

# .env ファイルから環境変数を読み込み
load_dotenv()

# 接続パラメータを取得
neo4j_uri = os.getenv("NEO4J_URI")
neo4j_user = os.getenv("NEO4J_USER")
neo4j_password = os.getenv("NEO4J_PASSWORD")
qdrant_host = os.getenv("QDRANT_HOST")
qdrant_port = int(os.getenv("QDRANT_PORT"))
qdrant_collection = os.getenv("QDRANT_COLLECTION")
```

## 接続問題のトラブルシューティング

### Neo4j 接続の問題

1. **接続拒否**:
   - Neo4j が実行中であることを確認
   - 正しいポートを確認（このセットアップでは 7688）
   - http://localhost:7474 の Neo4j ブラウザで直接接続を試行

2. **認証失敗**:
   - ユーザー名とパスワードを確認
   - Neo4j の設定で認証が有効になっているか確認

3. **タイムアウト**:
   - ネットワーク接続を確認
   - Neo4j が長時間実行クエリで過負荷になっていないか確認

### Qdrant 接続の問題

1. **接続拒否**:
   - Qdrant が実行中であることを確認
   - 正しいポートを確認（このセットアップでは 6335）
   - Qdrant API に直接接続を試行: http://localhost:6335/dashboard

2. **コレクションが見つからない**:
   - コレクション名が正しいことを確認（"document_chunks"）
   - Qdrant ダッシュボードでコレクションが存在するか確認

3. **バージョン互換性**:
   - クライアントバージョン間の非推奨メソッドに関する警告は正常
   - サンプルに示されたバージョン対応コードを使用

## 参考リソース

- [Neo4j Driver Documentation](https://neo4j.com/docs/api/python-driver/current/)
- [Qdrant Client Documentation](https://qdrant.tech/documentation/quick-start/)
- [Sentence-Transformers Documentation](https://www.sbert.net/)
- [データベース接続テストレポート](../test_db_connection/index.md)
