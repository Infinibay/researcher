#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colors & helpers ────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
step()  { echo -e "\n${CYAN}${BOLD}==> $1${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}!${NC} $1"; }
err()   { echo -e "  ${RED}✗${NC} $1"; }
die()   { err "$1"; exit 1; }

# ── Configuration ───────────────────────────────────────────────────────────
OLLAMA_MODEL="qwen3-coder:30b"
OLLAMA_EMBED_MODEL="nomic-embed-text"
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
DB_DIR="$SCRIPT_DIR/.data"
DB_PATH="$DB_DIR/pabada.db"
VENV_DIR="$SCRIPT_DIR/.venv"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

FORGEJO_ADMIN_USER="pabada"
FORGEJO_ADMIN_PASSWORD="${FORGEJO_ADMIN_PASSWORD:-pabada123}"
FORGEJO_ADMIN_EMAIL="pabada@local.dev"
FORGEJO_TOKEN_NAME="pabada-token"
FORGEJO_TOKEN_FILE="$DB_DIR/forgejo_token"

# PID file for cleanup
PID_FILE="$SCRIPT_DIR/.pids"
: > "$PID_FILE"

cleanup() {
    echo ""
    step "Shutting down"
    if [ -f "$PID_FILE" ]; then
        while IFS= read -r pid; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
                ok "Stopped PID $pid"
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    ok "Done"
}
trap cleanup EXIT INT TERM

# ── 1. Ollama ───────────────────────────────────────────────────────────────
step "Ollama"

command -v ollama &>/dev/null || die "ollama not found in PATH. Install from https://ollama.ai"

# Start ollama serve if not already running
if ! curl -sf "$OLLAMA_HOST/api/tags" &>/dev/null; then
    warn "Ollama not running — starting ollama serve"
    ollama serve &>/dev/null &
    echo $! >> "$PID_FILE"
    # Wait for it to be ready
    for i in $(seq 1 30); do
        if curl -sf "$OLLAMA_HOST/api/tags" &>/dev/null; then
            break
        fi
        sleep 1
    done
    curl -sf "$OLLAMA_HOST/api/tags" &>/dev/null || die "Ollama failed to start after 30s"
    ok "Ollama started"
else
    ok "Ollama already running"
fi

# Pull models if not present
pull_if_missing() {
    local model="$1"
    if ollama list 2>/dev/null | grep -q "^${model}"; then
        ok "Model ${model} already downloaded"
    else
        warn "Pulling ${model} (this may take a while)..."
        ollama pull "$model"
        ok "Model ${model} ready"
    fi
}

pull_if_missing "$OLLAMA_MODEL"
pull_if_missing "$OLLAMA_EMBED_MODEL"

# ── 2. Forgejo ──────────────────────────────────────────────────────────────
step "Forgejo (local git server)"

FORGEJO_SKIP=false

# 2a. Check Docker availability
if ! command -v docker &>/dev/null; then
    warn "docker not found in PATH — skipping Forgejo"
    FORGEJO_SKIP=true
elif ! docker compose version &>/dev/null; then
    warn "docker compose plugin not available — skipping Forgejo"
    FORGEJO_SKIP=true
fi

if [ "$FORGEJO_SKIP" = false ]; then
    # 2b. Start Forgejo container
    mkdir -p "$DB_DIR/forgejo"
    docker compose up -d forgejo

    echo -n "  Waiting for Forgejo "
    FORGEJO_READY=false
    for i in $(seq 1 30); do
        if curl -sf http://localhost:3000 &>/dev/null; then
            FORGEJO_READY=true
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""

    if [ "$FORGEJO_READY" = false ]; then
        die "Forgejo failed to start after 60s"
    fi
    ok "Forgejo running at http://localhost:3000"

    # 2c. Create admin user (idempotent)
    docker exec forgejo forgejo admin user create \
        --username "$FORGEJO_ADMIN_USER" \
        --password "$FORGEJO_ADMIN_PASSWORD" \
        --email "$FORGEJO_ADMIN_EMAIL" \
        --admin \
        --must-change-password=false 2>/dev/null || true
    ok "Admin user '$FORGEJO_ADMIN_USER' ready"

    # 2d. Mint or reuse API token
    FORGEJO_TOKEN=""
    if [ -f "$FORGEJO_TOKEN_FILE" ] && [ -s "$FORGEJO_TOKEN_FILE" ]; then
        FORGEJO_TOKEN=$(cat "$FORGEJO_TOKEN_FILE")
        ok "API token loaded from cache"
    else
        # Try to create a new token
        TOKEN_RESPONSE=$(curl -sf -X POST \
            -u "$FORGEJO_ADMIN_USER:$FORGEJO_ADMIN_PASSWORD" \
            -H "Content-Type: application/json" \
            -d "{\"name\":\"$FORGEJO_TOKEN_NAME\"}" \
            "http://localhost:3000/api/v1/users/$FORGEJO_ADMIN_USER/tokens" 2>/dev/null) || {
            # Token name already exists — delete and retry
            curl -sf -X DELETE \
                -u "$FORGEJO_ADMIN_USER:$FORGEJO_ADMIN_PASSWORD" \
                "http://localhost:3000/api/v1/users/$FORGEJO_ADMIN_USER/tokens/$FORGEJO_TOKEN_NAME" 2>/dev/null || true
            TOKEN_RESPONSE=$(curl -sf -X POST \
                -u "$FORGEJO_ADMIN_USER:$FORGEJO_ADMIN_PASSWORD" \
                -H "Content-Type: application/json" \
                -d "{\"name\":\"$FORGEJO_TOKEN_NAME\"}" \
                "http://localhost:3000/api/v1/users/$FORGEJO_ADMIN_USER/tokens" 2>/dev/null) || die "Failed to create Forgejo API token"
        }
        FORGEJO_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['sha1'])")
        echo "$FORGEJO_TOKEN" > "$FORGEJO_TOKEN_FILE"
        chmod 600 "$FORGEJO_TOKEN_FILE"
        ok "API token created and cached"
    fi
else
    warn "Forgejo skipped — git hosting will not be available"
fi

# ── 3. Python venv ──────────────────────────────────────────────────────────
step "Python environment"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    ok "Created .venv"
fi
source "$VENV_DIR/bin/activate"
ok "Activated .venv ($(python3 --version))"

# Install deps if crewai is missing (lightweight check)
if ! python3 -c "import crewai" &>/dev/null; then
    step "Installing Python dependencies"
    pip install -q crewai'[tools]' fastapi uvicorn pydantic-settings chromadb openai
    ok "Dependencies installed"
else
    ok "Python dependencies present"
fi

# ── 4. Database ─────────────────────────────────────────────────────────────
step "Database"

mkdir -p "$DB_DIR"

if [ ! -f "$DB_PATH" ]; then
    SCHEMA_FILE="$SCRIPT_DIR/backend/db/schema.sql"
    if [ ! -f "$SCHEMA_FILE" ]; then
        die "Schema file not found: $SCHEMA_FILE"
    fi
    python3 -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
conn.executescript(open('$SCHEMA_FILE').read())
conn.execute('PRAGMA journal_mode = WAL')
conn.close()
print('Database initialized')
"
    ok "Created database at $DB_PATH"
else
    ok "Database exists at $DB_PATH"
fi

# ── 5. Frontend ─────────────────────────────────────────────────────────────
step "Frontend"

if [ -d "$FRONTEND_DIR" ]; then
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        warn "Installing frontend dependencies (npm install)"
        (cd "$FRONTEND_DIR" && npm install --silent)
        ok "npm install complete"
    else
        ok "node_modules present"
    fi
else
    warn "No frontend/ directory — skipping"
fi

# ── 6. Environment variables ────────────────────────────────────────────────
step "Environment"

# Database
export PABADA_DB="$DB_PATH"

# Sandbox off for local dev (no container runtime needed)
export PABADA_SANDBOX_ENABLED="false"

# CrewAI — Ollama as OpenAI-compatible LLM provider
# Model name WITHOUT provider prefix so CrewAI routes to native OpenAI SDK
# Base URL with /v1 suffix for OpenAI-compatible endpoint
export OPENAI_API_KEY="ollama"
export OPENAI_API_BASE="${OLLAMA_HOST}/v1"
export OPENAI_MODEL_NAME="$OLLAMA_MODEL"

# Embeddings via Ollama
export PABADA_EMBEDDING_PROVIDER="ollama"
export PABADA_EMBEDDING_MODEL="$OLLAMA_EMBED_MODEL"
export PABADA_EMBEDDING_BASE_URL="$OLLAMA_HOST"

# RAG storage in local data dir
export PABADA_RAG_PERSIST_DIR="$DB_DIR/.chromadb"

# Forgejo
if [ "$FORGEJO_SKIP" = false ]; then
    export FORGEJO_API_URL="http://localhost:3000/api/v1"
    export FORGEJO_TOKEN="$FORGEJO_TOKEN"
    export FORGEJO_OWNER="$FORGEJO_ADMIN_USER"
    export FORGEJO_REPO=""  # agents will set this per-project
fi

ok "PABADA_DB=$DB_PATH"
ok "LLM=$OLLAMA_MODEL via ${OLLAMA_HOST}/v1"
ok "Embeddings=ollama/$OLLAMA_EMBED_MODEL"
if [ "$FORGEJO_SKIP" = false ]; then
    ok "Forgejo=http://localhost:3000 (user: $FORGEJO_ADMIN_USER)"
fi

# ── 7. Launch ───────────────────────────────────────────────────────────────
step "Starting services"

# Backend (FastAPI on :8000)
echo -e "  ${CYAN}Backend${NC}  → http://localhost:8000  (API + docs at /docs)"
python3 -m backend.api.run &
BACKEND_PID=$!
echo $BACKEND_PID >> "$PID_FILE"

# Wait for backend to be ready
for i in $(seq 1 15); do
    if curl -sf http://localhost:8000/api/health &>/dev/null; then
        break
    fi
    sleep 1
done

# Frontend dev server (Vite on :5173)
if [ -d "$FRONTEND_DIR" ]; then
    echo -e "  ${CYAN}Frontend${NC} → http://localhost:5173"
    (cd "$FRONTEND_DIR" && npm run dev -- --host 2>&1) &
    FRONTEND_PID=$!
    echo $FRONTEND_PID >> "$PID_FILE"
fi

echo ""
echo -e "${GREEN}${BOLD}=== PABADA Ready ===${NC}"
echo -e "  Frontend:   ${BOLD}http://localhost:5173${NC}"
echo -e "  Backend:    ${BOLD}http://localhost:8000${NC}"
echo -e "  API docs:   ${BOLD}http://localhost:8000/docs${NC}"
echo -e "  Ollama:     ${BOLD}$OLLAMA_HOST${NC}"
echo -e "  LLM:        ${BOLD}$OLLAMA_MODEL (via ${OLLAMA_HOST}/v1)${NC}"
echo -e "  Embeddings: ${BOLD}ollama/$OLLAMA_EMBED_MODEL${NC}"
if [ "$FORGEJO_SKIP" = false ]; then
    echo -e "  Forgejo:    ${BOLD}http://localhost:3000${NC}  (user: $FORGEJO_ADMIN_USER)"
fi
echo ""
echo -e "  Press ${BOLD}Ctrl+C${NC} to stop all services"
echo ""

# Wait for either process to exit
wait
