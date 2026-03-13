#!/bin/bash
# ========================================
#  GraphRAG Hybrid - サービス起動スクリプト
#  macOS / Linux 用
# ========================================
#
# 使い方:
#   ./start.sh              # データベース + Web UI を起動
#   ./start.sh mcp          # データベース + MCP サーバーを起動
#   ./start.sh all          # データベース + Web UI + MCP サーバーを起動
#   ./start.sh stop         # すべて停止
#   ./start.sh status       # 稼働状況を確認

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m'

step()  { echo -e "${CYAN}[*] $1${NC}"; }
ok()    { echo -e "${GREEN}[OK] $1${NC}"; }
warn()  { echo -e "${YELLOW}[!] $1${NC}"; }

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  GraphRAG Hybrid - Service Manager${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

case "${1:-ui}" in
    stop)
        step "サービスを停止しています..."
        # Streamlit / MCP プロセスを停止
        pkill -f "streamlit run app.py" 2>/dev/null && ok "Streamlit を停止しました。" || true
        pkill -f "python server.py" 2>/dev/null && ok "MCP サーバーを停止しました。" || true
        docker compose down
        ok "データベースを停止しました。"
        exit 0
        ;;

    status)
        step "サービス稼働状況:"
        echo ""
        echo -e "  ${CYAN}Docker コンテナ:${NC}"
        docker compose ps 2>/dev/null || warn "  Docker Compose が起動していません。"
        echo ""

        if curl -sf http://localhost:6333/health >/dev/null 2>&1; then
            ok "  Qdrant: 起動中 (http://localhost:6333)"
        else
            warn "  Qdrant: 停止中"
        fi

        if curl -sf http://localhost:7476 >/dev/null 2>&1; then
            ok "  Neo4j:  起動中 (http://localhost:7476)"
        else
            warn "  Neo4j:  停止中"
        fi

        if curl -sf http://localhost:8501 >/dev/null 2>&1; then
            ok "  Web UI: 起動中 (http://localhost:8501)"
        else
            warn "  Web UI: 停止中"
        fi
        echo ""
        exit 0
        ;;

    ui|mcp|all)
        # データベース起動
        step "データベースを起動しています..."
        docker compose up -d

        step "データベースの準備を待機しています..."
        WAITED=0
        while [ $WAITED -lt 60 ]; do
            if curl -sf http://localhost:6333/health >/dev/null 2>&1; then
                ok "データベースが起動しました。"
                break
            fi
            sleep 3
            WAITED=$((WAITED + 3))
            echo -e "${GRAY}  待機中... (${WAITED}秒)${NC}"
        done
        echo ""

        # サービス起動
        if [ "$1" = "all" ] || [ "$1" = "ui" ] || [ -z "$1" ]; then
            step "Web UI (Streamlit) を起動しています..."
            uv run streamlit run app.py &
            ok "Web UI: http://localhost:8501"
        fi

        if [ "$1" = "all" ] || [ "$1" = "mcp" ]; then
            step "MCP サーバーを起動しています..."
            uv run python server.py &
            ok "MCP サーバーを起動しました。"
        fi

        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  サービスが起動しました${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "  Web UI:  ${YELLOW}http://localhost:8501${NC}"
        echo -e "  Neo4j:   ${YELLOW}http://localhost:7476${NC}"
        echo -e "  Qdrant:  ${YELLOW}http://localhost:6333/dashboard${NC}"
        echo ""
        echo -e "  ${GRAY}停止するには: ./start.sh stop${NC}"
        echo ""

        # フォアグラウンドで待機
        wait
        ;;

    *)
        echo "使い方: $0 [ui|mcp|all|stop|status]"
        echo ""
        echo "  ui      Web UI を起動（デフォルト）"
        echo "  mcp     MCP サーバーを起動"
        echo "  all     Web UI + MCP サーバーを起動"
        echo "  stop    すべて停止"
        echo "  status  稼働状況を確認"
        exit 1
        ;;
esac
