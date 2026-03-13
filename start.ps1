<#
.SYNOPSIS
    GraphRAG Hybrid - サービス起動スクリプト (Windows)

.DESCRIPTION
    データベースと各種サービスを簡単に起動・停止できるスクリプトです。

.EXAMPLE
    .\start.ps1              # データベース + Web UI を起動
    .\start.ps1 -MCP         # データベース + MCP サーバーを起動
    .\start.ps1 -All         # データベース + Web UI + MCP サーバーを起動
    .\start.ps1 -Stop        # すべて停止
    .\start.ps1 -Status      # 稼働状況を確認
#>

param(
    [switch]$MCP,
    [switch]$All,
    [switch]$Stop,
    [switch]$Status
)

$ErrorActionPreference = "Continue"

function Write-Step  { param([string]$msg) Write-Host "[*] $msg" -ForegroundColor Cyan }
function Write-OK    { param([string]$msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn  { param([string]$msg) Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GraphRAG Hybrid - Service Manager" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- 停止 ---
if ($Stop) {
    Write-Step "サービスを停止しています..."

    # Streamlit / MCP プロセスを停止
    $procs = Get-Process -Name python -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "streamlit|server\.py" }
    if ($procs) {
        $procs | Stop-Process -Force
        Write-OK "Python プロセスを停止しました。"
    }

    docker compose down 2>&1 | Out-Host
    Write-OK "データベースを停止しました。"
    exit 0
}

# --- ステータス確認 ---
if ($Status) {
    Write-Step "サービス稼働状況:"
    Write-Host ""

    # Docker
    $containers = docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>$null
    if ($containers) {
        Write-Host "  Docker コンテナ:" -ForegroundColor White
        $containers | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    } else {
        Write-Warn "  Docker コンテナは起動していません。"
    }
    Write-Host ""

    # Qdrant
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:6333/health" -TimeoutSec 2 -ErrorAction Stop
        Write-OK "  Qdrant: 起動中 (http://localhost:6333)"
    } catch {
        Write-Warn "  Qdrant: 停止中"
    }

    # Neo4j
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:7476" -TimeoutSec 2 -ErrorAction Stop
        Write-OK "  Neo4j:  起動中 (http://localhost:7476)"
    } catch {
        Write-Warn "  Neo4j:  停止中"
    }

    # Streamlit
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:8501" -TimeoutSec 2 -ErrorAction Stop
        Write-OK "  Web UI: 起動中 (http://localhost:8501)"
    } catch {
        Write-Warn "  Web UI: 停止中"
    }

    Write-Host ""
    exit 0
}

# --- 起動 ---

# 1. Docker
Write-Step "データベースを起動しています..."
docker compose up -d 2>&1 | Out-Host

Write-Step "データベースの準備を待機しています..."
$waited = 0
$ready = $false
while ($waited -lt 60 -and -not $ready) {
    Start-Sleep -Seconds 3
    $waited += 3
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:6333/health" -TimeoutSec 2 -ErrorAction Stop
        $ready = $true
    } catch {
        Write-Host "  待機中... ($waited 秒)" -ForegroundColor Gray
    }
}
if ($ready) {
    Write-OK "データベースが起動しました。"
} else {
    Write-Warn "データベースの起動確認がタイムアウトしました。"
}

Write-Host ""

# 2. サービス起動
if ($All -or (-not $MCP)) {
    Write-Step "Web UI (Streamlit) を起動しています..."
    Start-Process -FilePath "uv" -ArgumentList "run", "streamlit", "run", "app.py" -WindowStyle Normal
    Write-OK "Web UI: http://localhost:8501"
}

if ($All -or $MCP) {
    Write-Step "MCP サーバーを起動しています..."
    Start-Process -FilePath "uv" -ArgumentList "run", "python", "server.py" -WindowStyle Normal
    Write-OK "MCP サーバーを起動しました。"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  サービスが起動しました" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Web UI:  http://localhost:8501" -ForegroundColor Yellow
Write-Host "  Neo4j:   http://localhost:7476" -ForegroundColor Yellow
Write-Host "  Qdrant:  http://localhost:6333/dashboard" -ForegroundColor Yellow
Write-Host ""
Write-Host "  停止するには: .\start.ps1 -Stop" -ForegroundColor Gray
Write-Host ""
