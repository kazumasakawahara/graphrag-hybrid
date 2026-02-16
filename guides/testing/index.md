# データベース接続テスト

このガイドでは、Neo4j と Qdrant データベースへの接続テストプロセスを文書化しています。

## 初期セットアップ

GraphRAG システムは両データベースに標準ポートを使用します：

- Neo4j は Bolt ポート 7687（標準ポート）で動作
- Qdrant は HTTP ポート 6333（標準ポート）で動作

## 環境設定

テスト用に以下の環境変数を使用してください：

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

## テストプロセス

接続テストプロセスでは以下を検証します：

1. 標準ポート 7687 での Neo4j 接続
2. デフォルト認証情報での Neo4j 認証
3. 標準ポート 6333 での Qdrant 接続
4. Qdrant コレクションの存在とアクセス

## テスト結果

テストにより以下が確認されました：
- Neo4j は標準 Bolt ポート 7687 で動作
- Qdrant は標準 HTTP ポート 6333 で動作
- 両データベースはアクセス可能で正しく設定されている
- ドキュメントチャンクは両システムに正しく保存されている

## デバッグメモ

テスト中に以下を検証しました：
- Neo4j 接続はデフォルトポート 7687 で動作
- Qdrant 接続はデフォルトポート 6333 で動作
- すべてのデータベース操作が期待通りに機能

## 接続情報

### Neo4j
- **ホスト**: localhost
- **Bolt ポート**: 7687
- **HTTP ポート**: 7474
- **ユーザー名**: neo4j
- **パスワード**: password

### Qdrant
- **ホスト**: localhost
- **HTTP ポート**: 6333
- **gRPC ポート**: 6334
- **コレクション**: document_chunks

## 環境変数

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

## クエリテスト

`scripts/testing/query_tester.py` スクリプトは、両データベースに対してさまざまなクエリを実行します：

```bash
python scripts/testing/query_tester.py
```

### 主要なデバッグ変更

接続セットアップ時に以下の調整が行われました：

- 設定用の環境変数読み込みを追加
- Qdrant クライアント互換性のためのバージョンハンドリングを追加
- 欠損プロパティのエラーハンドリングを追加
- 異なる API 実装のサポートを追加

## 接続パラメータ

現在の検証済み接続パラメータ：

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

これらのパラメータはすべてのスクリプトで使用され、`.env` ファイルに設定する必要があります。

## トラブルシューティング

接続が失敗した場合、以下を確認してください：

1. Docker コンテナが実行中であること: `docker ps | grep graphrag`
2. ポートが正しくマッピングされていること: `docker-compose ps`
3. 環境変数が実際の設定と一致していること
4. ファイアウォール/VPN でネットワークアクセスがブロックされていないこと

## 内容

- `scripts/testing/test_connections.py` - 両データベースへの接続を検証するメインテストスクリプト
- `guides/testing/connection_info.md` - 発見された接続情報のまとめ
- `scripts/testing/query_tester.py` - 両データベースに対する各種クエリパターンのテストスクリプト
- `guides/query_guide.md` - Neo4j と Qdrant データベースクエリの包括的ガイド
- `scripts/testing/query_guidelines.json` - 生成されたクエリガイドライン（JSON 形式）
- `guides/testing/index.md` - このドキュメントファイル

## テストプロセスと調査結果

### 接続検出プロセス

テストプロセスにより、いくつかの重要な設定の詳細が判明しました：

1. **非標準ポート**:
   - Neo4j は Bolt ポート 7688（デフォルト 7687 の代わり）で動作
   - Qdrant は HTTP ポート 6335（デフォルト 6333 の代わり）で動作

2. **バージョン互換性の問題**:
   - Qdrant クライアントバージョン（1.13.3）がサーバーバージョン（1.5.1）より新しい
   - バージョン間の API の違いに特別な対応が必要

### 遭遇したデバッグ問題

テストスクリプトの開発中に、以下の問題を遭遇し解決しました：

1. **Neo4j ポートの検出**
   - ポート 7687 への初期接続で「Connection refused」エラーが発生
   - 正しいポート（7688）を検出するためのマルチポートテストを追加

2. **Qdrant ポートの検出**
   - ポート 6333 への初期接続が失敗
   - 正しいポート（6335）を検出するためのマルチポートテストを追加

3. **Qdrant バージョン互換性**
   - バージョン非互換の警告（1.13.3 クライアント vs 1.5.1 サーバー）
   - `check_version=False` での初期修正試行が失敗（パラメータ未サポート）
   - Python の `warnings.filterwarnings()` を使用して警告を抑制

4. **バージョン間の Qdrant API 変更**
   - エラー: `'CollectionParams' object has no attribute 'vector_size'`
   - 異なる属性名をチェックするバージョン対応コードを追加
   - 欠損属性のフォールバック値を実装

5. **エラーハンドリングの改善**
   - すべての API 呼び出しに try/except ブロックを追加
   - 欠損プロパティのデフォルト値を作成
   - `vectors_count` と `dimension` の変数スコープの問題を修正

### 主要な接続情報

テスト結果に基づく正しい接続パラメータ：

```env
NEO4J_URI=bolt://localhost:7688
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
QDRANT_HOST=localhost
QDRANT_PORT=6335
```

## テストの実行

接続テストを実行するには：

```bash
# 依存パッケージが未インストールの場合
uv sync

# テストを実行
uv run python scripts/testing/test_connections.py
```

## データベースコンテンツ

テストにより以下が確認されました：

- **Neo4j**: 162 Document ノードと 2785 Content ノード（合計 3652 ノード）
- **Qdrant**: 2785 ベクトルを持つ「document_chunks」コレクション（次元 384）

## 連携の推奨事項

これらのデータベースと連携する際：

1. 上記の検証済み接続パラメータを常に使用する
2. Qdrant API の違いに対応するバージョン対応コードを実装する
3. 潜在的な API の不整合に対応する try/except ブロックを使用する
4. 必須パラメータ（ベクトル次元など）のフォールバックを追加する
5. サーバーバージョン（1.5.x）に合わせた Qdrant クライアントバージョンの固定を検討する

## 参考リソース

- [Neo4j Python Driver Documentation](https://neo4j.com/docs/api/python-driver/current/)
- [Qdrant Client Documentation](https://qdrant.tech/documentation/quick-start/)
- [GraphRAG 連携ガイド](../graphrag_integration_guide.md)
