@echo off
chcp 65001 >nul 2>&1

REM ========================================
REM  GraphRAG Hybrid - サービス起動
REM  コマンドプロンプト用 (.bat)
REM ========================================
REM
REM 使い方:
REM   start.bat          ... データベース + Web UI を起動
REM   start.bat mcp      ... データベース + MCP サーバーを起動
REM   start.bat stop     ... すべて停止
REM   start.bat status   ... 稼働状況を確認

echo.
echo ========================================
echo   GraphRAG Hybrid - Service Manager
echo ========================================
echo.

if "%1"=="stop" goto :STOP
if "%1"=="status" goto :STATUS

REM --- データベース起動 ---
echo [*] データベースを起動しています...
docker compose up -d
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker Desktop が起動しているか確認してください。
    pause
    exit /b 1
)

echo [*] データベースの準備を待機しています...
timeout /t 15 /nobreak >nul
echo [OK] データベースが起動しました。
echo.

if "%1"=="mcp" (
    echo [*] MCP サーバーを起動しています...
    start "GraphRAG MCP Server" uv run python server.py
    echo [OK] MCP サーバーを起動しました。
) else (
    echo [*] Web UI (Streamlit) を起動しています...
    start "GraphRAG Web UI" uv run streamlit run app.py
    echo [OK] Web UI を起動しました: http://localhost:8501
)

echo.
echo ========================================
echo   サービスが起動しました
echo ========================================
echo.
echo   Web UI:  http://localhost:8501
echo   Neo4j:   http://localhost:7476
echo   Qdrant:  http://localhost:6333/dashboard
echo.
echo   停止するには: start.bat stop
echo.
pause
goto :EOF

:STOP
echo [*] サービスを停止しています...
taskkill /FI "WINDOWTITLE eq GraphRAG*" /F >nul 2>&1
docker compose down
echo [OK] すべてのサービスを停止しました。
pause
goto :EOF

:STATUS
echo [*] サービス稼働状況:
echo.
docker compose ps 2>nul
echo.
pause
goto :EOF
