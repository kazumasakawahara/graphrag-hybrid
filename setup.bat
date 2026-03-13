@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ========================================
REM  GraphRAG Hybrid - Windows セットアップ
REM  コマンドプロンプト用 (.bat)
REM ========================================
REM
REM PowerShell が使える場合は setup.ps1 の利用を推奨します。
REM このスクリプトはコマンドプロンプトしか使えない環境向けです。

echo.
echo ========================================
echo   GraphRAG Hybrid - Setup (Windows)
echo ========================================
echo.

REM --- 前提条件チェック ---
echo [*] 前提条件を確認しています...

set MISSING=0

where git >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Git が見つかりません。
    echo         https://git-scm.com/download/win からインストールしてください。
    set MISSING=1
) else (
    echo [OK] Git が見つかりました。
)

where docker >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker が見つかりません。
    echo         https://www.docker.com/products/docker-desktop/ からインストールしてください。
    set MISSING=1
) else (
    echo [OK] Docker が見つかりました。
)

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python が見つかりません。
    echo         https://www.python.org/downloads/ からインストールしてください。
    set MISSING=1
) else (
    echo [OK] Python が見つかりました。
)

where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] uv が見つかりません。インストールを試みます...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    where uv >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] uv のインストールに失敗しました。
        echo         コマンドプロンプトを再起動して再実行してください。
        set MISSING=1
    ) else (
        echo [OK] uv をインストールしました。
    )
) else (
    echo [OK] uv が見つかりました。
)

if %MISSING% equ 1 (
    echo.
    echo [ERROR] 不足しているツールをインストールしてから再実行してください。
    pause
    exit /b 1
)

echo.

REM --- .env ファイル作成 ---
echo [*] .env ファイルを確認しています...

if exist ".env" (
    echo [OK] .env ファイルは既に存在します。スキップします。
) else (
    echo [*] .env ファイルを作成しています...
    (
        echo # --- Neo4j グラフデータベース ---
        echo NEO4J_URI=bolt://localhost:7689
        echo NEO4J_USER=neo4j
        echo NEO4J_PASSWORD=graphrag123
        echo NEO4J_DATABASE=neo4j
        echo.
        echo # --- Qdrant ベクトルデータベース ---
        echo QDRANT_HOST=localhost
        echo QDRANT_PORT=6333
        echo QDRANT_GRPC_PORT=6334
        echo QDRANT_PREFER_GRPC=true
        echo QDRANT_COLLECTION=document_chunks
        echo.
        echo # --- 埋め込みモデル ---
        echo EMBEDDING_MODEL=intfloat/multilingual-e5-base
        echo EMBEDDING_DIMENSION=768
        echo EMBEDDING_DEVICE=cpu
        echo EMBEDDING_MAX_LENGTH=512
        echo.
        echo # --- ドキュメントチャンキング ---
        echo CHUNK_SIZE=800
        echo CHUNK_OVERLAP=150
        echo.
        echo # --- Gemini API（エンティティ抽出用、任意） ---
        echo # GEMINI_API_KEY=your_api_key_here
    ) > .env
    echo [OK] .env ファイルを作成しました。
)

echo.

REM --- Docker でデータベース起動 ---
echo [*] Docker でデータベースを起動しています...

docker compose up -d
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker Compose の実行に失敗しました。
    echo         Docker Desktop が起動しているか確認してください。
    pause
    exit /b 1
)
echo [OK] Neo4j と Qdrant を起動しました。

echo [*] データベースの起動を待機しています...
timeout /t 15 /nobreak >nul
echo [OK] 待機完了。

echo.

REM --- Python 依存関係 ---
echo [*] Python 依存関係をインストールしています...
echo     初回は数分かかります（埋め込みモデルのダウンロードを含む）。

uv sync
if %ERRORLEVEL% neq 0 (
    echo [ERROR] 依存関係のインストールに失敗しました。
    pause
    exit /b 1
)
echo [OK] 依存関係のインストールが完了しました。

echo.

REM --- 完了 ---
echo ========================================
echo   セットアップ完了!
echo ========================================
echo.
echo 次のステップ:
echo.
echo   1. Web UI を起動:
echo      uv run streamlit run app.py
echo.
echo   2. ドキュメントを取り込み:
echo      uv run python scripts/import_docs.py --docs-dir .\your_docs_here --recursive
echo.
echo   3. MCP サーバーを起動 (Claude Desktop 連携):
echo      uv run python server.py
echo.
echo   4. データベースの管理画面:
echo      Neo4j:  http://localhost:7476
echo      Qdrant: http://localhost:6333/dashboard
echo.

pause
