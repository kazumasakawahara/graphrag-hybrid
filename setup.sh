#!/bin/bash
# ========================================
#  GraphRAG Hybrid - セットアップスクリプト
#  macOS / Linux 用
# ========================================
#
# 使い方:
#   ./setup.sh
#   ./setup.sh --skip-docker
#   ./setup.sh --gemini-key YOUR_KEY

set -e

# --- 色付きメッセージ ---
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m'

step()  { echo -e "${CYAN}[*] $1${NC}"; }
ok()    { echo -e "${GREEN}[OK] $1${NC}"; }
warn()  { echo -e "${YELLOW}[!] $1${NC}"; }
err()   { echo -e "${RED}[ERROR] $1${NC}"; }

# --- 引数解析 ---
SKIP_DOCKER=false
GEMINI_KEY=""

for arg in "$@"; do
    case $arg in
        --skip-docker) SKIP_DOCKER=true ;;
        --gemini-key=*) GEMINI_KEY="${arg#*=}" ;;
        --gemini-key) shift; GEMINI_KEY="$1" ;;
    esac
done

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  GraphRAG Hybrid - Setup${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# =========================================================
# 1. 前提条件チェック
# =========================================================
step "前提条件を確認しています..."

MISSING=0

# Git
if command -v git &>/dev/null; then
    ok "Git: $(git --version)"
else
    err "Git が見つかりません。"
    MISSING=1
fi

# Docker
if [ "$SKIP_DOCKER" = false ]; then
    if command -v docker &>/dev/null; then
        if docker info &>/dev/null; then
            ok "Docker: $(docker version --format '{{.Client.Version}}' 2>/dev/null)"
        else
            warn "Docker コマンドは見つかりましたが、Docker デーモンが起動していません。"
            warn "Docker Desktop を起動してから再実行してください。"
        fi
    else
        err "Docker が見つかりません。https://www.docker.com/products/docker-desktop/ からインストールしてください。"
        MISSING=1
    fi
fi

# Python
if command -v python3 &>/dev/null; then
    ok "Python: $(python3 --version)"
elif command -v python &>/dev/null; then
    ok "Python: $(python --version)"
else
    err "Python が見つかりません。"
    MISSING=1
fi

# uv
if command -v uv &>/dev/null; then
    ok "uv: $(uv --version)"
else
    warn "uv が見つかりません。インストールを試みます..."
    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        export PATH="$HOME/.local/bin:$PATH"
        if command -v uv &>/dev/null; then
            ok "uv をインストールしました。"
        else
            err "uv のインストール後にパスが通りません。シェルを再起動してください。"
            MISSING=1
        fi
    else
        err "uv のインストールに失敗しました。"
        err "手動でインストール: curl -LsSf https://astral.sh/uv/install.sh | sh"
        MISSING=1
    fi
fi

if [ $MISSING -ne 0 ]; then
    echo ""
    err "不足しているツールをインストールしてから再実行してください。"
    exit 1
fi

echo ""

# =========================================================
# 2. .env ファイルの作成
# =========================================================
step ".env ファイルを確認しています..."

if [ -f ".env" ]; then
    ok ".env ファイルは既に存在します。スキップします。"
else
    step ".env ファイルを作成しています..."

    cat > .env << 'ENVEOF'
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
ENVEOF

    if [ -n "$GEMINI_KEY" ]; then
        sed -i.bak "s/# GEMINI_API_KEY=your_api_key_here/GEMINI_API_KEY=$GEMINI_KEY/" .env
        rm -f .env.bak
    fi

    ok ".env ファイルを作成しました。"

    if [ -z "$GEMINI_KEY" ]; then
        warn "Gemini API キーが未設定です（エンティティ抽出は無効）。"
        warn "後から .env ファイルの GEMINI_API_KEY を編集して有効化できます。"
    fi
fi

echo ""

# =========================================================
# 3. データベースの起動
# =========================================================
if [ "$SKIP_DOCKER" = false ]; then
    step "Docker でデータベースを起動しています..."

    docker compose up -d

    ok "Neo4j と Qdrant を起動しました。"
    echo -e "${GRAY}  Neo4j ブラウザ:       http://localhost:7476${NC}"
    echo -e "${GRAY}  Qdrant ダッシュボード: http://localhost:6333/dashboard${NC}"

    step "データベースの起動を待機しています (最大60秒)..."
    WAITED=0
    READY=false
    while [ $WAITED -lt 60 ] && [ "$READY" = false ]; do
        sleep 3
        WAITED=$((WAITED + 3))
        if curl -sf http://localhost:6333/health >/dev/null 2>&1; then
            READY=true
        else
            echo -e "${GRAY}  待機中... (${WAITED}秒)${NC}"
        fi
    done
    if [ "$READY" = true ]; then
        ok "データベースが起動しました。"
    else
        warn "データベースの起動確認がタイムアウトしました。手動で確認してください。"
    fi
else
    warn "Docker の起動をスキップしました (--skip-docker)。"
fi

echo ""

# =========================================================
# 4. Python 依存関係のインストール
# =========================================================
step "Python 依存関係をインストールしています..."
echo -e "${GRAY}  初回は埋め込みモデル (~1GB) のダウンロードがあるため、数分かかります。${NC}"

uv sync

ok "依存関係のインストールが完了しました。"

echo ""

# =========================================================
# 5. セットアップ完了
# =========================================================
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  セットアップ完了!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}次のステップ:${NC}"
echo ""
echo -e "  1. Web UI を起動:"
echo -e "     ${YELLOW}uv run streamlit run app.py${NC}"
echo ""
echo -e "  2. ドキュメントを取り込み（コマンドライン）:"
echo -e "     ${YELLOW}uv run python scripts/import_docs.py --docs-dir ./your_docs_here --recursive${NC}"
echo ""
echo -e "  3. MCP サーバーを起動（Claude Desktop 連携）:"
echo -e "     ${YELLOW}uv run python server.py${NC}"
echo ""
echo -e "  4. データベースの管理画面:"
echo -e "     ${YELLOW}Neo4j:  http://localhost:7476${NC}"
echo -e "     ${YELLOW}Qdrant: http://localhost:6333/dashboard${NC}"
echo ""
