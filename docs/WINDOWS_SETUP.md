# Windows セットアップガイド

GraphRAG Hybrid を Windows 環境で利用するための手順です。

## 必要なソフトウェア

| ソフトウェア | 用途 | ダウンロード |
|-------------|------|-------------|
| **Docker Desktop** | データベース (Neo4j, Qdrant) の実行 | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Git** | ソースコードの取得 | [git-scm.com](https://git-scm.com/download/win) |
| **Python 3.10+** | アプリケーション実行環境 | [python.org](https://www.python.org/downloads/) |
| **Claude Desktop** (任意) | AI エージェント連携 | [claude.ai](https://claude.ai/download) |

> **Python インストール時の注意**: インストーラーで **「Add Python to PATH」にチェック** を入れてください。

## クイックスタート (PowerShell)

### ステップ 1: ソースコードの取得

PowerShell を開き（スタートメニューで「PowerShell」と検索）、以下を実行:

```powershell
git clone https://github.com/kazumasakawahara/graphrag-hybrid.git
cd graphrag-hybrid
```

### ステップ 2: Docker Desktop の起動

Docker Desktop アプリケーションを起動してください。タスクバーにクジラのアイコンが表示され、「Docker Desktop is running」と表示されれば準備完了です。

### ステップ 3: セットアップスクリプトの実行

```powershell
.\setup.ps1
```

このスクリプトが以下を自動で行います:
1. 必要なツール (Git, Docker, Python, uv) の確認
2. `uv` が未インストールの場合は自動インストール
3. `.env` 設定ファイルの生成
4. データベース (Neo4j + Qdrant) の起動
5. Python 依存関係のインストール

> **初回は 5-10 分かかります**（AI 埋め込みモデル約 1GB のダウンロードを含む）。

### ステップ 4: 動作確認

```powershell
.\start.ps1
```

ブラウザで http://localhost:8501 が開き、GraphRAG の Web UI が表示されれば成功です。

## スクリプト一覧

### セットアップ

| スクリプト | 形式 | 説明 |
|-----------|------|------|
| `setup.ps1` | PowerShell | 初期セットアップ（推奨） |
| `setup.bat` | コマンドプロンプト | PowerShell が使えない環境向け |

#### setup.ps1 のオプション

```powershell
.\setup.ps1                              # 通常セットアップ
.\setup.ps1 -SkipDocker                  # Docker 起動をスキップ
.\setup.ps1 -SkipDeps                    # 依存関係インストールをスキップ
.\setup.ps1 -GeminiApiKey "YOUR_KEY"     # Gemini API キーを設定
```

### サービス管理

| スクリプト | 形式 | 説明 |
|-----------|------|------|
| `start.ps1` | PowerShell | サービスの起動・停止・状態確認 |
| `start.bat` | コマンドプロンプト | 同上（コマンドプロンプト版） |

#### start.ps1 の使い方

```powershell
.\start.ps1              # データベース + Web UI を起動
.\start.ps1 -MCP         # データベース + MCP サーバーを起動
.\start.ps1 -All         # データベース + Web UI + MCP サーバーを起動
.\start.ps1 -Stop        # すべて停止
.\start.ps1 -Status      # 稼働状況を確認
```

#### start.bat の使い方

```cmd
start.bat              REM データベース + Web UI を起動
start.bat mcp          REM データベース + MCP サーバーを起動
start.bat stop         REM すべて停止
start.bat status       REM 稼働状況を確認
```

### Claude Desktop 連携

```powershell
.\configure-claude.ps1
```

Claude Desktop の設定ファイルに GraphRAG MCP サーバーを自動登録します。実行後、Claude Desktop を再起動すると GraphRAG の検索ツールが利用可能になります。

## 実行ポリシーについて

PowerShell スクリプト (`.ps1`) の実行がブロックされる場合:

```powershell
# 現在のユーザーに対してスクリプト実行を許可（一度だけ実行すれば OK）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

または、個別のスクリプトだけ実行する場合:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

## トラブルシューティング

### 「docker compose」でエラーが出る

**原因**: Docker Desktop が起動していない、または WSL 2 バックエンドが有効でない。

**対処**:
1. Docker Desktop を起動する
2. Settings → General → 「Use the WSL 2 based engine」にチェック
3. Docker Desktop を再起動

### 「uv: コマンドが見つかりません」

**原因**: uv のインストール後にパスが反映されていない。

**対処**:
1. PowerShell / コマンドプロンプトを閉じて再度開く
2. それでも解決しない場合: `$env:Path` に `%USERPROFILE%\.local\bin` を追加

### Web UI のサイドバーに「Neo4j: 未接続」と表示される

**原因**: データベースの起動が完了していない。

**対処**:
1. `.\start.ps1 -Status` で状態を確認
2. 停止していれば `docker compose up -d` で再起動
3. 数秒待ってブラウザをリロード

### 初回起動が非常に遅い

**原因**: 正常です。初回はAI埋め込みモデル（約1GB）のダウンロードが行われます。

**対処**: 2回目以降はモデルがキャッシュされるため高速に起動します。

### ポート競合エラー

**原因**: 他のアプリケーションが同じポートを使用している。

**使用ポート一覧**:
| ポート | サービス | 確認コマンド |
|-------|---------|-------------|
| 7476 | Neo4j ブラウザ | `netstat -ano \| findstr :7476` |
| 7689 | Neo4j Bolt | `netstat -ano \| findstr :7689` |
| 6333 | Qdrant REST | `netstat -ano \| findstr :6333` |
| 6334 | Qdrant gRPC | `netstat -ano \| findstr :6334` |
| 8501 | Streamlit UI | `netstat -ano \| findstr :8501` |

## よくある質問

### Q: WSL は必要ですか？

**A**: いいえ。Docker Desktop for Windows が WSL 2 バックエンドを内部的に使用しますが、ユーザーが WSL を直接操作する必要はありません。すべてのコマンドは PowerShell またはコマンドプロンプトから実行できます。

### Q: Mac / Linux 用のスクリプトはありますか？

**A**: はい。`setup.sh` と `start.sh` が同等の機能を提供します。

```bash
chmod +x setup.sh start.sh
./setup.sh
./start.sh
```

### Q: GPU は必要ですか？

**A**: いいえ。デフォルトでは CPU で動作します。GPU (CUDA) を使用する場合は `.env` で `EMBEDDING_DEVICE=cuda` に変更してください。
