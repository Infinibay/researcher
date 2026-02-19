"""Centralized configuration for PABADA tools."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DB_PATH: str = os.environ.get("PABADA_DB", "/research/pabada.db")
    MAX_RETRIES: int = 5
    RETRY_BASE_DELAY: float = 0.1  # 100ms

    # Timeouts
    COMMAND_TIMEOUT: int = 60
    WEB_TIMEOUT: int = 30
    GIT_PUSH_TIMEOUT: int = 120
    CHAT_POLL_INTERVAL: float = 2.0

    # Sandbox
    SANDBOX_ENABLED: bool = True
    ALLOWED_BASE_DIRS: list[str] = ["/research"]
    ALLOWED_COMMANDS: list[str] = [
        "git", "python", "python3", "pip", "npm", "node", "npx", "fnm",
        "pytest", "make", "cargo", "rustc", "rustup", "go", "javac", "java",
        "ls", "cat", "head", "tail", "wc", "diff", "find", "grep",
        "mkdir", "cp", "mv", "rm", "touch", "chmod",
        "curl", "wget",
        "tar", "unzip", "gzip",
        "pdflatex", "bibtex", "latexmk",
    ]

    # Container sandbox
    SANDBOX_IMAGE: str = "pabada-sandbox:latest"
    SANDBOX_CONTAINER_RUNTIME: str | None = None  # None = auto-detect
    WORKSPACE_BASE_DIR: str = "/research/workspaces"
    CLEANUP_INTERVAL_SECONDS: int = 300
    SANDBOX_NETWORK: str = "none"  # "none" | "host" | custom network name

    # File limits
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10MB
    MAX_DIR_LISTING: int = 1000

    # Web search
    WEB_SEARCH_MAX_RESULTS: int = 10
    WEB_CACHE_TTL_SECONDS: int = 3600  # 1 hour

    # LLM (used by CrewAI agents)
    # For Ollama: MODEL="llama3.2", LLM_BASE_URL="http://host.containers.internal:11434/v1", LLM_API_KEY="ollama"
    # For OpenAI: MODEL="gpt-4.1-mini", LLM_API_KEY="sk-..."
    # For Anthropic: MODEL="anthropic/claude-sonnet-4-5-20250929", LLM_API_KEY="sk-ant-..."
    LLM_MODEL: str = os.environ.get("MODEL", "")
    LLM_BASE_URL: str = os.environ.get("OPENAI_API_BASE", "")
    LLM_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

    # Embedding / Knowledge
    EMBEDDING_PROVIDER: str = "openai"  # openai, azure, google, ollama
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_BASE_URL: str | None = None  # Override for Ollama/local
    KNOWLEDGE_CHUNK_SIZE: int = 1000  # Characters per chunk
    KNOWLEDGE_CHUNK_OVERLAP: int = 200  # Overlap between chunks

    # RAG
    RAG_PERSIST_DIR: str = "/research/.chromadb"
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.3

    # NL2SQL
    NL2SQL_ROW_LIMIT: int = 100
    NL2SQL_MAX_ROW_LIMIT: int = 500
    NL2SQL_TIMEOUT: int = 10

    # Code Interpreter
    CODE_INTERPRETER_TIMEOUT: int = 120
    CODE_INTERPRETER_MAX_OUTPUT: int = 50000

    # Forgejo (local git server)
    FORGEJO_API_URL: str = os.environ.get("FORGEJO_API_URL", "")
    FORGEJO_TOKEN: str = os.environ.get("FORGEJO_TOKEN", "")
    FORGEJO_OWNER: str = os.environ.get("FORGEJO_OWNER", "pabada")

    # Anti-Loop System
    LOOP_GUARD_ENABLED: bool = True
    LOOP_DEDUP_WINDOW_SECONDS: int = 300
    LOOP_DEDUP_SIMILARITY_THRESHOLD: float = 0.7
    LOOP_RATE_PER_THREAD: int = 5
    LOOP_RATE_PER_THREAD_WINDOW: int = 60
    LOOP_RATE_GLOBAL: int = 20
    LOOP_RATE_GLOBAL_WINDOW: int = 300
    LOOP_PING_PONG_THRESHOLD: int = 4
    LOOP_REPEAT_THRESHOLD: int = 3
    LOOP_CIRCUIT_THRESHOLD: int = 3
    LOOP_CIRCUIT_COOLDOWN: int = 60

    model_config = {"env_prefix": "PABADA_"}


settings = Settings()
