<#
.SYNOPSIS
    GraphRAG Hybrid - Windows セットアップスクリプト (PowerShell)

.DESCRIPTION
    Neo4j + Qdrant ハイブリッド GraphRAG システムの初期セットアップを行います。
    - 必要ツール (Git, Docker, uv) の確認
    - Python 依存関係のインストール
    - .env ファイルの生成
    - データベースの起動
    - 動作確認

.EXAMPLE
    .\setup.ps1
    .\setup.ps1 -SkipDocker
    .\setup.ps1 -GeminiApiKey "YOUR_KEY"

.NOTES
    Windows 10/11 + PowerShell 5.1 以上で動作します。
    管理者権限は不要です（Docker Desktop が事前にインストール済みの場合）。
#>

param(
    [switch]$SkipDocker,
    [switch]$SkipDeps,
    [string]$GeminiApiKey = ""
)

$ErrorActionPreference = "Stop"

# --- 色付きメッセージ ---
function Write-Step  { param([string]$msg) Write-Host "[*] $msg" -ForegroundColor Cyan }
function Write-OK    { param([string]$msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn  { param([string]$msg) Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GraphRAG Hybrid - Setup (Windows)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# =========================================================
# 1. 前提条件チェック
# =========================================================
Write-Step "前提条件を確認しています..."

$missing = @()

# Git
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVer = git --version
    Write-OK "Git: $gitVer"
} else {
    $missing += "Git"
    Write-Err "Git が見つかりません。https://git-scm.com/download/win からインストールしてください。"
}

# Docker
if (-not $SkipDocker) {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        try {
            $dockerVer = docker version --format '{{.Client.Version}}' 2>$null
            Write-OK "Docker: $dockerVer"
        } catch {
            Write-Warn "Docker コマンドは見つかりましたが、Docker Desktop が起動していない可能性があります。"
            Write-Warn "Docker Desktop を起動してから再実行してください。"
        }
    } else {
        $missing += "Docker"
        Write-Err "Docker が見つかりません。https://www.docker.com/products/docker-desktop/ からインストールしてください。"
    }
}

# Python
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = python --version 2>&1
    Write-OK "Python: $pyVer"
} else {
    $missing += "Python"
    Write-Err "Python が見つかりません。https://www.python.org/downloads/ からインストールしてください。"
}

# uv
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVer = uv --version 2>&1
    Write-OK "uv: $uvVer"
} else {
    Write-Warn "uv が見つかりません。インストールを試みます..."
    try {
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        # PATH を再読み込み
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            Write-OK "uv をインストールしました。"
        } else {
            $missing += "uv"
            Write-Err "uv のインストールに失敗しました。PowerShell を再起動して再実行してください。"
        }
    } catch {
        $missing += "uv"
        Write-Err "uv の自動インストールに失敗しました。"
        Write-Err "手動でインストール: powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Err "以下のツールが不足しています: $($missing -join ', ')"
    Write-Err "インストール後、このスクリプトを再実行してください。"
    exit 1
}

Write-Host ""

# =========================================================
# 2. .env ファイルの作成
# =========================================================
Write-Step ".env ファイルを確認しています..."

if (Test-Path ".env") {
    Write-OK ".env ファイルは既に存在します。スキップします。"
} else {
    Write-Step ".env ファイルを作成しています..."

    $envContent = @"
# --- Neo4j グラフデータベース ---
NEO4J_URI=bolt://localhost:7689
NEO4J_USER=neo4j
NEO4J_PASSWORD=graphrag123
NEO4J_DATABASE=neo4j

# --- Qdrant ベクトルデータベース ---
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_PREFER_GRPC=true
QDRANT_COLLECTION=document_chunks

# --- 埋め込みモデル ---
EMBEDDING_MODEL=intfloat/multilingual-e5-base
EMBEDDING_DIMENSION=768
EMBEDDING_DEVICE=cpu
EMBEDDING_MAX_LENGTH=512

# --- ドキュメントチャンキング ---
CHUNK_SIZE=800
CHUNK_OVERLAP=150

# --- Gemini API（エンティティ抽出用、任意） ---
# GEMINI_API_KEY=your_api_key_here
"@

    if ($GeminiApiKey -ne "") {
        $envContent = $envContent -replace "# GEMINI_API_KEY=your_api_key_here", "GEMINI_API_KEY=$GeminiApiKey"
    }

    $envContent | Out-File -FilePath ".env" -Encoding utf8NoBOM
    Write-OK ".env ファイルを作成しました。"

    if ($GeminiApiKey -eq "") {
        Write-Warn "Gemini API キーが未設定です（エンティティ抽出は無効）。"
        Write-Warn "後から .env ファイルの GEMINI_API_KEY を編集して有効化できます。"
    }
}

Write-Host ""

# =========================================================
# 3. データベースの起動
# =========================================================
if (-not $SkipDocker) {
    Write-Step "Docker でデータベースを起動しています..."

    try {
        docker compose up -d 2>&1 | Out-Host
        Write-OK "Neo4j と Qdrant を起動しました。"
        Write-Host "  Neo4j ブラウザ:  http://localhost:7476" -ForegroundColor Gray
        Write-Host "  Qdrant ダッシュボード: http://localhost:6333/dashboard" -ForegroundColor Gray

        Write-Step "データベースの起動を待機しています (最大60秒)..."
        $waited = 0
        $ready = $false
        while ($waited -lt 60 -and -not $ready) {
            Start-Sleep -Seconds 3
            $waited += 3
            try {
                $null = Invoke-WebRequest -Uri "http://localhost:6333/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
                $ready = $true
            } catch {
                Write-Host "  待機中... ($waited 秒)" -ForegroundColor Gray
            }
        }
        if ($ready) {
            Write-OK "データベースが起動しました。"
        } else {
            Write-Warn "データベースの起動確認がタイムアウトしました。手動で確認してください。"
        }
    } catch {
        Write-Err "Docker Compose の実行に失敗しました: $_"
        Write-Err "Docker Desktop が起動しているか確認してください。"
    }
} else {
    Write-Warn "Docker の起動をスキップしました (-SkipDocker)。"
}

Write-Host ""

# =========================================================
# 4. Python 依存関係のインストール
# =========================================================
if (-not $SkipDeps) {
    Write-Step "Python 依存関係をインストールしています..."
    Write-Host "  初回は埋め込みモデル (~1GB) のダウンロードがあるため、数分かかります。" -ForegroundColor Gray

    try {
        uv sync 2>&1 | Out-Host
        Write-OK "依存関係のインストールが完了しました。"
    } catch {
        Write-Err "依存関係のインストールに失敗しました: $_"
        exit 1
    }
} else {
    Write-Warn "依存関係のインストールをスキップしました (-SkipDeps)。"
}

Write-Host ""

# =========================================================
# 5. セットアップ完了
# =========================================================
Write-Host "========================================" -ForegroundColor Green
Write-Host "  セットアップ完了!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "次のステップ:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Web UI を起動:" -ForegroundColor White
Write-Host "     uv run streamlit run app.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2. ドキュメントを取り込み（コマンドライン）:" -ForegroundColor White
Write-Host "     uv run python scripts/import_docs.py --docs-dir .\your_docs_here --recursive" -ForegroundColor Yellow
Write-Host ""
Write-Host "  3. MCP サーバーを起動（Claude Desktop 連携）:" -ForegroundColor White
Write-Host "     uv run python server.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "  4. データベースの管理画面:" -ForegroundColor White
Write-Host "     Neo4j:  http://localhost:7476" -ForegroundColor Yellow
Write-Host "     Qdrant: http://localhost:6333/dashboard" -ForegroundColor Yellow
Write-Host ""
