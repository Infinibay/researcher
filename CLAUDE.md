# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PABADA is an AI-powered project management system that uses multi-agent teams (via CrewAI) to autonomously manage software projects. Agents gather requirements, plan work, write code, review code, conduct research, and brainstorm — orchestrated by event-driven flows.

## Commands

### Full stack (local dev)
```bash
./start.sh  # Starts Ollama, Forgejo, creates venv, inits DB, launches backend (:8000) + frontend (:5173)
```

### Forgejo (local git server)
Forgejo starts automatically with `./start.sh` (requires Docker).
- UI:  http://localhost:3000  (admin: pabada / pabada123)
- API: http://localhost:3000/api/v1
- Token cached at: `.data/forgejo_token`
- To restart manually: `docker compose up -d forgejo`
- To stop: `docker compose stop forgejo`

### Backend only
```bash
source .venv/bin/activate
python -m backend.api.run  # FastAPI + uvicorn with reload on :8000
```

### Frontend only
```bash
cd frontend
npm run dev      # Vite dev server on :5173 (proxies /api to :8000)
npm run build    # tsc + vite build
```

### Tests
```bash
uv run pytest                         # all tests
uv run pytest backend/tests/test_foo.py  # single file
uv run pytest -k "test_name"          # single test by name
```
- `asyncio_mode = "auto"` — async tests need no decorator
- Tests use isolated in-memory SQLite via autouse fixture (monkeypatches `PABADA_DB`)

## Architecture

### Backend (`backend/`)

**FastAPI REST/WebSocket layer** on top of **CrewAI Flows + Agents**.

Key directories:
- `flows/` — The heart of the system. Flow classes use `@start()`, `@listen()`, `@router()` decorators with Pydantic state models. Flows run in daemon threads managed by `FlowManager`.
- `agents/` — Agent factory functions (`create_X_agent()`) returning `PabadaAgent` wrappers. Registry manages roster CRUD, name generation, run tracking.
- `tools/` — 15+ tool categories. All inherit `PabadaBaseTool(BaseTool, ABC)`. Stateless; get context from thread-local context vars (`tools/base/context.py`). Return JSON strings via `_success(data)` / `_error(message)`.
- `prompts/` — Per-role directories with `system.py` (identity/backstory) and `tasks.py` (task descriptions). Dynamic context injected via `build_team_section()` and `build_state_context()`.
- `api/` — FastAPI app, route modules, WebSocket manager.
- `db/` — SQLite schema (`schema.sql`) and migrations. 26+ tables with FTS5 virtual tables.
- `communication/` — Inter-agent messaging and thread manager.
- `state/` — Task state machine, dependency validator, progress tracking.
- `security/` — Container sandbox and workspace manager.
- `config/settings.py` — All config via `pydantic_settings.BaseSettings` with `PABADA_` env prefix.
- `git/` — (planned) `RepositoryManager` will use `settings.FORGEJO_API_URL` and `settings.FORGEJO_TOKEN` to mirror local repos to Forgejo.

**Event system**: SQLite triggers → `events_log` table → background listener threads poll and emit `FlowEvent` objects to a global `EventBus` singleton → WebSocket manager relays to frontend.

**DB access pattern**: All database calls go through `execute_with_retry(fn, ...)` in `tools/base/db.py` — never raw sqlite3. Uses exponential backoff for SQLITE_BUSY. WAL mode always on.

**Agent IDs**: Deterministic format — `{role}_p{project_id}` (single-instance) or `{role}_{n}_p{project_id}` (multi-instance, e.g., `developer_1_p1`).

### Frontend (`frontend/src/`)

React 19 + TypeScript + Vite SPA.

- `api/client.ts` — `fetchApi<T>()` wrapper (no axios). WebSocket singleton `wsManager` in `api/websocket.ts`.
- `hooks/` — One custom hook per resource (`useTasks`, `useProjects`, etc.) using `@tanstack/react-query`.
- `stores/` — Zustand stores with localStorage persistence (project selection, activity feed).
- `components/` — Pages, layout, tasks, wiki, common UI. TailwindCSS utility classes throughout.

### Data flow
```
User (browser) → React UI → fetchApi/WebSocket → FastAPI routes → FlowManager → CrewAI Flows → Agents → Tools → SQLite
                                                                                     ↓
                                                                               SQLite triggers → events_log → EventBus → WebSocket → UI
```

## Environment Variables

All backend config uses `PABADA_` prefix. Key vars:
```
PABADA_DB              # SQLite path (default: .data/pabada.db)
PABADA_SANDBOX_ENABLED # Container sandbox (false for local dev)
PABADA_LLM_MODEL       # LLM model name
PABADA_LLM_BASE_URL    # LLM endpoint
PABADA_LLM_API_KEY     # LLM API key
PABADA_EMBEDDING_PROVIDER  # ollama | openai | azure | google
PABADA_EMBEDDING_MODEL
PABADA_EMBEDDING_BASE_URL
```
CrewAI also reads `OPENAI_API_KEY`, `OPENAI_API_BASE`, `OPENAI_MODEL_NAME` directly.

Forgejo (no `PABADA_` prefix — exported directly by `start.sh`):
```
FORGEJO_API_URL    # Forgejo REST API base (http://localhost:3000/api/v1)
FORGEJO_TOKEN      # Admin API token (auto-generated by start.sh, cached in .data/forgejo_token)
FORGEJO_OWNER      # Forgejo username that owns repos (default: pabada)
FORGEJO_REPO       # Per-project repo name (set by agents at runtime)
```

## Prompt Design

See `PROMPT_DESIGN.md` for canonical principles. Key rules:
- System prompts define identity, team roster, and communication protocol (static per invocation)
- Task prompts define what to do with dynamic context
- Every scenario the agent might encounter must have a clear instruction — zero dead spots
- Dynamic context injected via `build_team_section()` and `build_state_context()` from `backend/prompts/team.py`

## Task State Machine

`backlog → pending → in_progress → review_ready → done` (also `rejected`, `cancelled`)

Task types: `plan, research, code, review, test, design, integrate, documentation, bug_fix`
