# GraphRAG ソースコード

このディレクトリには、GraphRAG ハイブリッド検索システムのコアソースコードが含まれています。

## モジュール構成

- `__init__.py` - パッケージ初期化
- `config.py` - 設定管理と環境変数の読み込み

### サブディレクトリ

- `processors/` - ドキュメント処理コンポーネント
  - `markdown_processor.py` - Markdown ドキュメントの処理とチャンク分割

- `utils/` - ユーティリティ関数とヘルパー
  - `neo4j_utils.py` - Neo4j データベースユーティリティ
  - `qdrant_utils.py` - Qdrant ベクトルデータベースユーティリティ
  - `query_utils.py` - ハイブリッドシステムのクエリインターフェース
  - `text_utils.py` - テキスト処理ユーティリティ

## コアコンポーネント

### ドキュメント処理

ドキュメント処理パイプラインが担当する処理：

- Markdown ファイルの読み込みと解析
- テキストのセマンティック単位へのチャンク分割
- メタデータと関係性の抽出
- トピックの識別

### データベースユーティリティ

データベースユーティリティが提供する機能：

- Neo4j と Qdrant の接続管理
- スキーマのセットアップと検証
- クエリビルダーと結果プロセッサー
- トランザクション管理

### クエリエンジン

クエリインターフェースがサポートする検索：

- セマンティック検索とグラフベース検索のハイブリッド検索
- より豊富な結果のためのコンテキスト拡張
- トピックとカテゴリによるフィルタリング
- ドキュメント関係の探索

## コードの使用方法

必要に応じてモジュールをインポートしてください：

```python
from src.config import load_config
from src.utils.neo4j_utils import Neo4jHelper
from src.utils.qdrant_utils import QdrantHelper
from src.utils.query_utils import QueryEngine
from src.processors.markdown_processor import MarkdownProcessor

# 使用例
config = load_config()
neo4j = Neo4jHelper(config)
qdrant = QdrantHelper(config)
query_engine = QueryEngine(neo4j, qdrant)
```
