<#
.SYNOPSIS
    Claude Desktop に GraphRAG MCP サーバーを自動登録するスクリプト

.DESCRIPTION
    Claude Desktop の設定ファイル (claude_desktop_config.json) に
    GraphRAG MCP サーバーの接続情報を追加します。

.EXAMPLE
    .\configure-claude.ps1
#>

$ErrorActionPreference = "Stop"

function Write-Step  { param([string]$msg) Write-Host "[*] $msg" -ForegroundColor Cyan }
function Write-OK    { param([string]$msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn  { param([string]$msg) Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Claude Desktop MCP 設定ツール" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- uv のパスを取得 ---
$uvPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uvPath) {
    # よくあるインストール先を確認
    $candidates = @(
        "$env:USERPROFILE\.local\bin\uv.exe",
        "$env:LOCALAPPDATA\uv\uv.exe",
        "$env:PROGRAMFILES\uv\uv.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $uvPath = $c
            break
        }
    }
}

if (-not $uvPath) {
    Write-Err "uv が見つかりません。先に setup.ps1 を実行してください。"
    exit 1
}

Write-OK "uv のパス: $uvPath"

# --- プロジェクトパスを取得 ---
$projectPath = (Get-Location).Path
Write-OK "プロジェクトパス: $projectPath"

# --- Claude Desktop 設定ファイルのパス ---
$configPath = "$env:APPDATA\Claude\claude_desktop_config.json"
$configDir = Split-Path $configPath

Write-Step "Claude Desktop 設定ファイルを確認しています..."

# ディレクトリが存在しない場合は作成
if (-not (Test-Path $configDir)) {
    Write-Warn "Claude Desktop の設定ディレクトリが見つかりません。作成します。"
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
}

# 既存の設定を読み込み
$config = @{}
if (Test-Path $configPath) {
    try {
        $config = Get-Content $configPath -Raw | ConvertFrom-Json -AsHashtable
        Write-OK "既存の設定ファイルを読み込みました。"
    } catch {
        Write-Warn "既存の設定ファイルの解析に失敗しました。新規作成します。"
        # バックアップ
        Copy-Item $configPath "$configPath.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
        $config = @{}
    }
} else {
    Write-Warn "設定ファイルが存在しません。新規作成します。"
}

# mcpServers キーが存在しない場合は作成
if (-not $config.ContainsKey("mcpServers")) {
    $config["mcpServers"] = @{}
}

# Windows パスのバックスラッシュをエスケープ
$serverPyPath = Join-Path $projectPath "server.py"

# GraphRAG MCP サーバーの設定
$graphragConfig = @{
    command = $uvPath
    args = @("run", "--directory", $projectPath, "python", $serverPyPath)
}

# 既存の設定があるか確認
if ($config["mcpServers"].ContainsKey("graphrag")) {
    Write-Warn "graphrag の設定は既に存在します。上書きしますか？"
    $response = Read-Host "  上書きする場合は 'y' を入力してください [y/N]"
    if ($response -ne "y") {
        Write-OK "設定の変更をスキップしました。"
        exit 0
    }
}

$config["mcpServers"]["graphrag"] = $graphragConfig

# 設定を書き込み
$json = $config | ConvertTo-Json -Depth 10
$json | Out-File -FilePath $configPath -Encoding utf8NoBOM

Write-OK "Claude Desktop の設定を更新しました。"
Write-Host ""
Write-Host "  設定ファイル: $configPath" -ForegroundColor Gray
Write-Host ""
Write-Host "  登録内容:" -ForegroundColor White
Write-Host "    サーバー名: graphrag" -ForegroundColor Gray
Write-Host "    コマンド:   $uvPath" -ForegroundColor Gray
Write-Host "    引数:       run --directory $projectPath python $serverPyPath" -ForegroundColor Gray
Write-Host ""
Write-Warn "Claude Desktop を再起動すると設定が反映されます。"
Write-Host ""
