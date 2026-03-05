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

# ── Load .env if present ───────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# ── Configuration ───────────────────────────────────────────────────────────
PABADA_LLM_PROVIDER="${PABADA_LLM_PROVIDER:-ollama}"

# Ollama defaults (only used when provider=ollama)
OLLAMA_MODEL="${PABADA_LLM_MODEL:-qwen3-coder:30b}"
OLLAMA_MODEL="${OLLAMA_MODEL#ollama_chat/}"  # strip LiteLLM provider prefix
OLLAMA_MODEL="${OLLAMA_MODEL#ollama/}"       # also handle ollama/ prefix
OLLAMA_EMBED_MODEL="${PABADA_EMBEDDING_MODEL:-nomic-embed-text}"
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
        # Phase 1: send SIGTERM to all tracked processes and their children
        while IFS= read -r pid; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
                pkill -P "$pid" 2>/dev/null || true
            fi
        done < "$PID_FILE"

        # Phase 2: wait up to 10s for processes to exit gracefully
        GRACE=10
        ALL_DEAD=false
        for i in $(seq 1 $GRACE); do
            ALL_DEAD=true
            while IFS= read -r pid; do
                if kill -0 "$pid" 2>/dev/null; then
                    ALL_DEAD=false
                    break
                fi
            done < "$PID_FILE"
            if [ "$ALL_DEAD" = true ]; then
                break
            fi
            echo -n "."
            sleep 1
        done
        echo ""

        # Phase 3: force-kill any survivors
        if [ "$ALL_DEAD" = false ]; then
            warn "Some processes did not exit gracefully — force killing"
            while IFS= read -r pid; do
                if kill -0 "$pid" 2>/dev/null; then
                    pkill -9 -P "$pid" 2>/dev/null || true
                    kill -9 "$pid" 2>/dev/null || true
                fi
            done < "$PID_FILE"
        fi

        rm -f "$PID_FILE"
    fi
    ok "Done"
}
trap cleanup EXIT INT TERM

# ── 1. LLM Provider ────────────────────────────────────────────────────────
step "LLM Provider ($PABADA_LLM_PROVIDER)"

OLLAMA_NEEDED=false
if [ "$PABADA_LLM_PROVIDER" = "ollama" ]; then
    OLLAMA_NEEDED=true
fi
# Embedding provider: defaults to "ollama" when LLM is ollama, "default" otherwise
if [ -z "${PABADA_EMBEDDING_PROVIDER:-}" ]; then
    if [ "$PABADA_LLM_PROVIDER" = "ollama" ]; then
        EMBED_PROVIDER="ollama"
    else
        EMBED_PROVIDER="default"
    fi
else
    EMBED_PROVIDER="$PABADA_EMBEDDING_PROVIDER"
fi
if [ "$EMBED_PROVIDER" = "ollama" ]; then
    OLLAMA_NEEDED=true
fi

if [ "$OLLAMA_NEEDED" = true ]; then
    command -v ollama &>/dev/null || die "ollama not found in PATH (needed for provider=$PABADA_LLM_PROVIDER). Install from https://ollama.ai"

    # Start ollama serve if not already running
    if ! curl -sf "$OLLAMA_HOST/api/tags" &>/dev/null; then
        warn "Ollama not running — starting ollama serve"
        ollama serve &>/dev/null &
        echo $! >> "$PID_FILE"
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
        # Use 'ollama show' which exits 0 if model exists locally,
        # non-zero otherwise. More reliable than parsing 'ollama list'.
        if ollama show "$model" &>/dev/null; then
            ok "Model ${model} already downloaded"
        else
            warn "Pulling ${model} (this may take a while)..."
            ollama pull "$model"
            ok "Model ${model} ready"
        fi
    }

    if [ "$PABADA_LLM_PROVIDER" = "ollama" ]; then
        pull_if_missing "$OLLAMA_MODEL"
    fi
    if [ "$EMBED_PROVIDER" = "ollama" ]; then
        pull_if_missing "$OLLAMA_EMBED_MODEL"
    fi
else
    ok "Using $PABADA_LLM_PROVIDER (no Ollama needed)"
fi

# ── 2. Forgejo ──────────────────────────────────────────────────────────────
step "Forgejo (local git server)"

FORGEJO_SKIP=false
CONTAINER_RT=""
COMPOSE_CMD=""

# 2a. Check container runtime availability (Docker or Podman)
if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
    CONTAINER_RT="docker"
    COMPOSE_CMD="docker compose"
elif command -v podman-compose &>/dev/null; then
    CONTAINER_RT="podman"
    COMPOSE_CMD="podman-compose"
elif command -v podman &>/dev/null && podman compose version &>/dev/null 2>&1; then
    CONTAINER_RT="podman"
    COMPOSE_CMD="podman compose"
else
    warn "neither docker nor podman found — skipping Forgejo"
    FORGEJO_SKIP=true
fi

if [ "$FORGEJO_SKIP" = false ]; then
    # 2b. Start Forgejo container
    mkdir -p "$DB_DIR/forgejo"

    # Force-recreate if data dir is fresh (no app.ini yet)
    if [ ! -f "$DB_DIR/forgejo/gitea/conf/app.ini" ]; then
        warn "Fresh Forgejo data directory — recreating container"
        $COMPOSE_CMD down forgejo 2>/dev/null || true
        $COMPOSE_CMD up -d --force-recreate forgejo
    else
        $COMPOSE_CMD up -d forgejo
    fi

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

    # 2b'. Fix data ownership — Forgejo web runs as 'git' (uid 1000 in container)
    # but the entrypoint creates files as root. Ensure git owns everything.
    $CONTAINER_RT exec forgejo chown -R git:git /data/git /data/gitea 2>/dev/null || true

    # 2c. Create admin user (idempotent)
    $CONTAINER_RT exec --user git forgejo forgejo admin user create \
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
            -d "{\"name\":\"$FORGEJO_TOKEN_NAME\",\"scopes\":[\"all\"]}" \
            "http://localhost:3000/api/v1/users/$FORGEJO_ADMIN_USER/tokens" 2>/dev/null) || {
            # Token name already exists — delete and retry
            curl -sf -X DELETE \
                -u "$FORGEJO_ADMIN_USER:$FORGEJO_ADMIN_PASSWORD" \
                "http://localhost:3000/api/v1/users/$FORGEJO_ADMIN_USER/tokens/$FORGEJO_TOKEN_NAME" 2>/dev/null || true
            TOKEN_RESPONSE=$(curl -sf -X POST \
                -u "$FORGEJO_ADMIN_USER:$FORGEJO_ADMIN_PASSWORD" \
                -H "Content-Type: application/json" \
                -d "{\"name\":\"$FORGEJO_TOKEN_NAME\",\"scopes\":[\"all\"]}" \
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
    python3 -m pip install -q crewai'[tools]' fastapi uvicorn pydantic-settings chromadb openai litellm
    ok "Core dependencies installed"
fi

# Install provider-specific deps
case "$PABADA_LLM_PROVIDER" in
    gemini)
        if ! python3 -c "import google.genai" &>/dev/null; then
            python3 -m pip install -q 'crewai[google-genai]'
            ok "Installed crewai[google-genai] for Gemini provider"
        fi
        ;;
    anthropic)
        if ! python3 -c "import anthropic" &>/dev/null; then
            python3 -m pip install -q anthropic
            ok "Installed anthropic SDK"
        fi
        ;;
esac
ok "Python dependencies present"

# ── 4. Database ─────────────────────────────────────────────────────────────
step "Database"

mkdir -p "$DB_DIR"

SCHEMA_FILE="$SCRIPT_DIR/backend/db/schema.sql"
if [ ! -f "$SCHEMA_FILE" ]; then
    die "Schema file not found: $SCHEMA_FILE"
fi

if [ ! -f "$DB_PATH" ]; then
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
    # DB file exists — ensure schema is initialized (handles empty DB files)
    python3 -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
if 'projects' not in tables:
    print('Database file exists but schema is missing — initializing...')
    conn.executescript(open('$SCHEMA_FILE').read())
    conn.execute('PRAGMA journal_mode = WAL')
    conn.close()
    print('Schema initialized')
else:
    conn.close()
    print('Database exists with schema')
"
    ok "Database exists at $DB_PATH"
fi

# Run migrations on existing databases
python3 -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
conn.row_factory = sqlite3.Row
# Migration 8: add original_description column to projects
cols = [r[1] for r in conn.execute('PRAGMA table_info(projects)').fetchall()]
if 'original_description' not in cols:
    conn.execute('ALTER TABLE projects ADD COLUMN original_description TEXT')
    conn.execute('UPDATE projects SET original_description = description WHERE original_description IS NULL')
    conn.execute(\"INSERT OR IGNORE INTO schema_migrations(version, name) VALUES (8, 'add_original_description_to_projects')\")
    conn.commit()
    print('Migration 8: added original_description column')
conn.close()
"

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

# Sandbox — defaults to false for local dev; override in .env
export PABADA_SANDBOX_ENABLED="${PABADA_SANDBOX_ENABLED:-false}"

# RAG storage in local data dir
export PABADA_RAG_PERSIST_DIR="$DB_DIR/.chromadb"

# ── LLM configuration (provider-dependent) ──
# Only PABADA_* vars are exported — Python's backend/config/llm.py handles
# provider env vars (OPENAI_API_KEY, GEMINI_API_KEY, etc.) internally.
case "$PABADA_LLM_PROVIDER" in
    ollama)
        export PABADA_LLM_MODEL="${PABADA_LLM_MODEL:-$OLLAMA_MODEL}"
        export PABADA_LLM_BASE_URL="${OLLAMA_HOST}"
        export PABADA_LLM_API_KEY="${PABADA_LLM_API_KEY:-ollama}"
        LLM_DISPLAY="${PABADA_LLM_MODEL} via ${OLLAMA_HOST}"
        ;;
    gemini)
        : "${PABADA_LLM_API_KEY:?Set PABADA_LLM_API_KEY in .env}"
        export PABADA_LLM_MODEL="${PABADA_LLM_MODEL:-gemini/gemini-2.0-flash}"
        export PABADA_LLM_BASE_URL=""
        LLM_DISPLAY="${PABADA_LLM_MODEL} (Gemini API)"
        ;;
    openai)
        : "${PABADA_LLM_API_KEY:?Set PABADA_LLM_API_KEY in .env}"
        export PABADA_LLM_MODEL="${PABADA_LLM_MODEL:-gpt-4.1-mini}"
        export PABADA_LLM_BASE_URL=""
        LLM_DISPLAY="${PABADA_LLM_MODEL} (OpenAI API)"
        ;;
    anthropic)
        : "${PABADA_LLM_API_KEY:?Set PABADA_LLM_API_KEY in .env}"
        export PABADA_LLM_MODEL="${PABADA_LLM_MODEL:-anthropic/claude-sonnet-4-5-20250929}"
        export PABADA_LLM_BASE_URL=""
        LLM_DISPLAY="${PABADA_LLM_MODEL} (Anthropic API)"
        ;;
    deepseek)
        : "${PABADA_LLM_API_KEY:?Set PABADA_LLM_API_KEY in .env}"
        export PABADA_LLM_MODEL="${PABADA_LLM_MODEL:-deepseek/deepseek-chat}"
        export PABADA_LLM_BASE_URL=""
        LLM_DISPLAY="${PABADA_LLM_MODEL} (DeepSeek API)"
        ;;
    zai)
        : "${PABADA_LLM_API_KEY:?Set PABADA_LLM_API_KEY in .env}"
        export PABADA_LLM_MODEL="${PABADA_LLM_MODEL:-zai/glm-4.7-flash}"
        export PABADA_LLM_BASE_URL=""
        LLM_DISPLAY="${PABADA_LLM_MODEL} (Zhipu AI API)"
        ;;
    local)
        # Local llama-server or other OpenAI-compatible endpoint.
        # Start your server separately (e.g. ./qwen.sh llama) before running start.sh.
        : "${PABADA_LLM_MODEL:?Set PABADA_LLM_MODEL in .env}"
        : "${PABADA_LLM_BASE_URL:?Set PABADA_LLM_BASE_URL in .env}"
        export PABADA_LLM_API_KEY="${PABADA_LLM_API_KEY:-not-needed}"
        LLM_DISPLAY="${PABADA_LLM_MODEL} via ${PABADA_LLM_BASE_URL}"
        ;;
    *)
        die "Unknown LLM provider: $PABADA_LLM_PROVIDER (valid: ollama, gemini, openai, anthropic, deepseek, zai, local)"
        ;;
esac

# ── Embeddings configuration ──
case "$EMBED_PROVIDER" in
    ollama)
        export PABADA_EMBEDDING_PROVIDER="ollama"
        export PABADA_EMBEDDING_MODEL="${PABADA_EMBEDDING_MODEL:-$OLLAMA_EMBED_MODEL}"
        export PABADA_EMBEDDING_BASE_URL="$OLLAMA_HOST"
        EMBED_DISPLAY="ollama/${PABADA_EMBEDDING_MODEL}"
        ;;
    default)
        export PABADA_EMBEDDING_PROVIDER="default"
        EMBED_DISPLAY="chromadb built-in (no API)"
        ;;
    google)
        export PABADA_EMBEDDING_PROVIDER="google"
        export PABADA_EMBEDDING_MODEL="${PABADA_EMBEDDING_MODEL:-text-embedding-004}"
        EMBED_DISPLAY="google/${PABADA_EMBEDDING_MODEL}"
        ;;
    openai)
        export PABADA_EMBEDDING_PROVIDER="openai"
        export PABADA_EMBEDDING_MODEL="${PABADA_EMBEDDING_MODEL:-text-embedding-3-small}"
        EMBED_DISPLAY="openai/${PABADA_EMBEDDING_MODEL}"
        ;;
    *)
        export PABADA_EMBEDDING_PROVIDER="default"
        EMBED_DISPLAY="chromadb built-in (no API)"
        ;;
esac

# Forgejo
if [ "$FORGEJO_SKIP" = false ]; then
    export FORGEJO_API_URL="${FORGEJO_API_URL:-http://localhost:3000/api/v1}"
    export FORGEJO_TOKEN="$FORGEJO_TOKEN"
    export FORGEJO_OWNER="$FORGEJO_ADMIN_USER"
    export FORGEJO_REPO=""  # agents will set this per-project
fi

ok "PABADA_DB=$DB_PATH"
ok "LLM=$LLM_DISPLAY"
ok "Embeddings=$EMBED_DISPLAY"
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
echo -n "  Waiting for backend "
BACKEND_READY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/health &>/dev/null; then
        BACKEND_READY=true
        break
    fi
    echo -n "."
    sleep 1
done
echo ""
if [ "$BACKEND_READY" = true ]; then
    ok "Backend ready"
else
    warn "Backend not responding yet — starting frontend anyway"
fi

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
echo -e "  LLM:        ${BOLD}$LLM_DISPLAY${NC}"
echo -e "  Embeddings: ${BOLD}$EMBED_DISPLAY${NC}"
if [ "$OLLAMA_NEEDED" = true ]; then
    echo -e "  Ollama:     ${BOLD}$OLLAMA_HOST${NC}"
fi
if [ "$FORGEJO_SKIP" = false ]; then
    echo -e "  Forgejo:    ${BOLD}http://localhost:3000${NC}  (user: $FORGEJO_ADMIN_USER)"
fi
echo ""
echo -e "  Press ${BOLD}Ctrl+C${NC} to stop all services"
echo ""

# Wait for either process to exit
wait
