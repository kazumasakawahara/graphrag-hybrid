# GraphRAG エラーハンドリング

このガイドでは、GraphRAG システムとの統合時に発生する可能性のある一般的なエラーとその効果的な対処方法について説明します。

## 接続エラー

### Neo4j 接続の問題

1. **接続拒否**

```python
from neo4j.exceptions import ServiceUnavailable

try:
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n)")
except ServiceUnavailable as e:
    if "Connection refused" in str(e):
        print("Neo4j is not running or wrong port")
    elif "unauthorized" in str(e).lower():
        print("Invalid credentials")
    else:
        print(f"Neo4j connection error: {str(e)}")
```

2. **認証失敗**

```python
from neo4j.exceptions import AuthError

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
except AuthError:
    print("Invalid Neo4j credentials")
```

### Qdrant 接続の問題

1. **接続タイムアウト**

```python
from qdrant_client.http.exceptions import UnexpectedResponse

try:
    client = QdrantClient(host=host, port=port)
    client.get_collection(collection_name)
except ConnectionError:
    print("Qdrant is not running or wrong port")
except UnexpectedResponse as e:
    if "404" in str(e):
        print(f"Collection '{collection_name}' not found")
    else:
        print(f"Qdrant error: {str(e)}")
```

2. **コレクションが見つからない**

```python
try:
    collection_info = client.get_collection(collection_name)
except UnexpectedResponse as e:
    if "404" in str(e):
        print(f"Creating collection '{collection_name}'...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
```

## クエリエラー

### エンベディング生成

1. **モデル読み込みエラー**

```python
from sentence_transformers import SentenceTransformer

try:
    model = SentenceTransformer(model_name)
except OSError as e:
    if "not found" in str(e):
        print(f"Model '{model_name}' not found. Downloading...")
        # モデルダウンロードロジックを実装
    else:
        print(f"Error loading model: {str(e)}")
```

2. **入力テキストエラー**

```python
def safe_encode(text: str) -> np.ndarray:
    try:
        if not isinstance(text, str):
            text = str(text)
        if not text.strip():
            raise ValueError("Empty input text")
        return model.encode(text)
    except Exception as e:
        print(f"Embedding generation error: {str(e)}")
        return None
```

### Qdrant 検索

1. **ベクトルサイズの不一致**

```python
def safe_search(query_vector: np.ndarray) -> List[Dict[Any, Any]]:
    try:
        collection_info = client.get_collection(collection_name)
        vector_size = collection_info.config.params.vectors.size

        if len(query_vector) != vector_size:
            raise ValueError(
                f"Query vector size {len(query_vector)} does not match "
                f"collection vector size {vector_size}"
            )

        return client.search(
            collection_name=collection_name,
            query_vector=query_vector.tolist(),
            limit=limit
        )
    except Exception as e:
        print(f"Qdrant search error: {str(e)}")
        return []
```

2. **バージョン互換性**

```python
def get_vectors_count(collection_info) -> int:
    """異なる Qdrant クライアントバージョンに対応"""
    try:
        return collection_info.vectors_count
    except AttributeError:
        try:
            return collection_info.points_count
        except AttributeError:
            return 0
```

### Neo4j クエリ

1. **Cypher 構文エラー**

```python
from neo4j.exceptions import CypherSyntaxError

def safe_query(session, query: str, params: Dict) -> List[Dict]:
    try:
        result = session.run(query, params)
        return [dict(record) for record in result]
    except CypherSyntaxError as e:
        print(f"Invalid Cypher query: {str(e)}")
        return []
    except Exception as e:
        print(f"Neo4j query error: {str(e)}")
        return []
```

2. **プロパティの欠落**

```python
def safe_get_property(node: Dict, prop: str, default: Any = None) -> Any:
    """デフォルト値付きでノードプロパティを安全に取得"""
    try:
        return node.get(prop, default)
    except Exception:
        return default
```

## エラーリカバリー

### 接続の復旧

```python
class ConnectionManager:
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def with_retry(self, func, *args, **kwargs):
        """リトライロジック付きで関数を実行"""
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(self.retry_delay)
```

### グレースフルデグラデーション

```python
class GraphRAGQuery:
    async def fallback_search(self, query: str) -> List[Dict[Any, Any]]:
        """Qdrant が失敗した場合に Neo4j のみの検索にフォールバック"""
        try:
            with self.manager.neo4j.driver.session() as session:
                # Neo4j でのテキストベース検索にフォールバック
                result = session.run("""
                    MATCH (d:Document)
                    WHERE d.content CONTAINS $query
                    RETURN d.doc_id as doc_id,
                           d.title as title,
                           d.content as content
                    LIMIT 5
                """, query=query)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"Fallback search failed: {str(e)}")
            return []
```

## モニタリングとロギング

### エラーロギング

```python
import logging
from datetime import datetime

class ErrorLogger:
    def __init__(self, log_file: str = "graphrag_errors.log"):
        logging.basicConfig(
            filename=log_file,
            level=logging.ERROR,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("GraphRAG")

    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """コンテキスト情報付きでエラーを記録"""
        error_info = {
            'timestamp': datetime.utcnow().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {}
        }
        self.logger.error(error_info)
```

### ヘルスチェック

```python
class HealthCheck:
    def __init__(self, manager):
        self.manager = manager

    async def check_health(self) -> Dict[str, Any]:
        """すべてのコンポーネントの正常性をチェック"""
        status = {
            'neo4j': {'status': 'unknown'},
            'qdrant': {'status': 'unknown'},
            'timestamp': datetime.utcnow().isoformat()
        }

        # Neo4j をチェック
        try:
            with self.manager.neo4j.driver.session() as session:
                result = session.run("RETURN 1")
                result.single()
                status['neo4j'] = {
                    'status': 'healthy',
                    'message': 'Connected successfully'
                }
        except Exception as e:
            status['neo4j'] = {
                'status': 'unhealthy',
                'error': str(e)
            }

        # Qdrant をチェック
        try:
            collection_info = self.manager.qdrant.client.get_collection(
                self.manager.collection_name
            )
            status['qdrant'] = {
                'status': 'healthy',
                'vectors_count': get_vectors_count(collection_info)
            }
        except Exception as e:
            status['qdrant'] = {
                'status': 'unhealthy',
                'error': str(e)
            }

        return status
```

## ベストプラクティス

1. すべてのデータベース操作に適切なエラーハンドリングを実装する
2. 一時的な障害にはリトライロジックを使用する
3. サービスが利用不可の場合はグレースフルデグラデーションを実装する
4. デバッグに十分なコンテキスト付きでエラーをログに記録する
5. システムの正常性を定期的にチェックする
6. バージョン互換性の問題に対応する
7. 処理前に入力データを検証する
8. リソースを適切にクリーンアップする
9. システムパフォーマンスを監視する
10. エラーメッセージをユーザーフレンドリーに保つ
