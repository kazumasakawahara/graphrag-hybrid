# GraphRAG スクリプト

このディレクトリには、GraphRAG システムのセットアップ、ドキュメントインポート、クエリ実行のためのスクリプトが含まれています。

## メインスクリプト

- `import_docs.py` - ドキュメントを Neo4j と Qdrant にインポートするメインスクリプト
- `query_demo.py` - ハイブリッドデータベースのクエリデモ
- `setup_databases.py` - Neo4j と Qdrant データベースのセットアップ
- `setup_neo4j_schema.py` - Neo4j データベーススキーマの作成
- `setup_qdrant_collection.py` - Qdrant コレクションの作成
- `verify_db_structure.py` - データベース構造の正当性検証

## 使用例

### システムのセットアップ：

```bash
# 両データベースに必要なスキーマ/コレクションを初期化
python scripts/setup_databases.py
```

### ドキュメントのインポート：

```bash
# your_docs_here ディレクトリからドキュメントをインポート
python scripts/import_docs.py --docs-dir ./your_docs_here
```

### システムへのクエリ：

```bash
# インタラクティブなクエリデモを実行
python scripts/query_demo.py
```

## テストスクリプト

`testing/` サブディレクトリには、データベース接続と機能をテストするための追加スクリプトがあります：

- `test_connections.py` - 両データベースへの接続テスト
- `query_tester.py` - 各種クエリ機能のテストとガイドライン生成
- `check_db.py` - Neo4j データベースの簡易チェック
- `check_qdrant.py` - Qdrant データベースの簡易チェック

## 重要事項

- すべてのスクリプトは `.env` ファイルが正しく設定されていることを前提としています
- 一部のスクリプトは追加の引数が必要です。`--help` を付けて実行すると詳細が表示されます
- スクリプトは常にプロジェクトルートディレクトリから実行してください
