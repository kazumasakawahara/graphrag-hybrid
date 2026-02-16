# データベース接続テスト

このディレクトリには、GraphRAG システムで使用する Neo4j と Qdrant データベースへの接続テスト用のスクリプトとドキュメントが含まれています。

## 内容

- `test_connections.py`: データベース接続とコンテンツ検証のメインテストスクリプト
- `connection_info.md`: 接続パラメータと調査結果のまとめ

## テストプロセスと調査結果

広範なテストにより、以下が判明しました：

1. **ポートの確認**:
   - Neo4j は標準ポートを使用：
     - HTTP ポート: 7474
     - Bolt ポート: 7687
   - Qdrant は標準ポートを使用：
     - HTTP ポート: 6333

2. **データベースコンテンツの検証**:
   - 両データベースへの接続に成功
   - Neo4j には 162 のドキュメント、約 20,112 のチャンクが含まれる
   - Qdrant には対応するドキュメント ID を持つ 20,112 のベクトルが含まれる

## 接続情報

データベース接続：

**Neo4j**
- HTTP ポート: 7474
- Bolt ポート: 7687
- 認証: neo4j/password

**Qdrant**
- HTTP ポート: 6333
- コレクション: document_chunks

## テストスクリプト

- `test_connections.py` - Neo4j と Qdrant 両データベースへの接続テスト

## テストの実行

データベース接続を検証するには：

```bash
# テストスクリプトを実行
uv run python test_db_connection/test_connections.py
```

## 期待される出力

テストが成功すると、スクリプトは以下を行います：

1. ポート 7687 で Neo4j に接続
2. 接続確認のための簡単なクエリを実行
3. Neo4j データベースのノード数をカウント
4. ポート 6333 で Qdrant に接続
5. Qdrant サービスの正常性を検証
6. 利用可能なコレクションを一覧表示
7. document_chunks コレクションの情報を表示

## トラブルシューティング

接続テストが失敗した場合：

1. Neo4j と Qdrant の両コンテナが実行中か確認：
   ```bash
   docker ps | grep graphrag
   ```

2. docker-compose.yml でポートが正しくマッピングされているか確認：
   ```bash
   cat docker-compose.yml | grep -E "7474|7687|6333"
   ```

3. .env ファイルに正しい接続情報があるか確認：
   ```bash
   cat .env | grep -E "NEO4J|QDRANT"
   ```

4. 必要なポートを他のサービスが使用していないか確認：
   ```bash
   lsof -i :7474 -i :7687 -i :6333
   ```
