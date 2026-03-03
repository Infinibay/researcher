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
    SANDBOX_ENABLED: bool = False
    ALLOWED_BASE_DIRS: list[str] = ["/research"]
    ALLOWED_COMMANDS: list[str] = [
        "git", "python", "python3", "pip", "npm", "node", "npx", "fnm",
        "pytest", "make", "cargo", "rustc", "rustup", "go", "javac", "java",
        "ls", "cat", "head", "tail", "wc", "diff", "find", "grep", "pwd",
        "mkdir", "cp", "mv", "rm", "touch", "chmod",
        "curl", "wget",
        "tar", "unzip", "gzip",
        "pdflatex", "bibtex", "latexmk",
    ]

    # Container sandbox
    SANDBOX_IMAGE: str = "pabada-sandbox:latest"
    SANDBOX_CONTAINER_RUNTIME: str | None = None  # None = auto-detect
    SANDBOX_GPU_ENABLED: bool = False  # Pass GPU devices into pods/containers
    WORKSPACE_BASE_DIR: str = os.environ.get(
        "PABADA_WORKSPACE_BASE_DIR",
        str(Path(__file__).resolve().parent.parent.parent / ".data" / "workspaces"),
    )
    CLEANUP_INTERVAL_SECONDS: int = 300
    SANDBOX_NETWORK: str = "slirp4netns"  # "none" | "slirp4netns" | "host" | custom network name

    # File limits
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10MB
    MAX_DIR_LISTING: int = 1000

    # Web search
    WEB_SEARCH_MAX_RESULTS: int = 10
    WEB_CACHE_TTL_SECONDS: int = 3600  # 1 hour
    WEB_RPM_LIMIT: int = 20  # max requests per minute across all web tools
    WEB_ROBOTS_CACHE_TTL: int = 3600  # TTL in seconds for robots.txt parser cache

    # SerperDev (primary web search)
    SERPER_API_KEY: str = ""
    SERPER_COUNTRY: str = ""  # country code to filter results (e.g. "us")
    SERPER_N_RESULTS: int = 10

    # Spider scraper (advanced, for JS-heavy sites)
    SPIDER_API_KEY: str = ""

    # Fallback web search
    WEB_SEARCH_FALLBACK_ENABLED: bool = True  # DDG as fallback when Serper fails

    # LLM (used by CrewAI agents via LiteLLM)
    # Model name — use LiteLLM format for non-OpenAI providers:
    #   ollama:    "qwen3-coder:30b"
    #   gemini:    "gemini/gemini-2.0-flash"
    #   openai:    "gpt-4.1-mini"
    #   anthropic: "anthropic/claude-sonnet-4-5-20250929"
    #   deepseek:  "deepseek/deepseek-chat"  (reasoner does NOT support tools)
    # Centralized LLM object: see backend/config/llm.py
    LLM_MODEL: str = ""
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_THINKING: bool = False  # Enable/disable thinking mode (Qwen3, etc.)

    # Memory (CrewAI native memory system)
    MEMORY_ENABLED: bool = True
    MEMORY_SCORE_THRESHOLD: float = 0.35

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

    # CI Gate
    CI_TEST_COMMAND: str = "pytest -x -q"

    # Anti-Loop System
    LOOP_GUARD_ENABLED: bool = True
    LOOP_DEDUP_WINDOW_SECONDS: int = 300
    LOOP_DEDUP_SIMILARITY_THRESHOLD: float = 0.7
    LOOP_RATE_PER_THREAD: int = 15
    LOOP_RATE_PER_THREAD_WINDOW: int = 60
    LOOP_RATE_GLOBAL: int = 40
    LOOP_RATE_GLOBAL_WINDOW: int = 300
    LOOP_PING_PONG_THRESHOLD: int = 10
    LOOP_REPEAT_THRESHOLD: int = 3
    LOOP_PAIR_EXCHANGE_MAX: int = 20       # max messages between same agent pair in window
    LOOP_PAIR_EXCHANGE_WINDOW: int = 300   # seconds
    LOOP_CIRCUIT_THRESHOLD: int = 3
    LOOP_CIRCUIT_COOLDOWN: int = 60

    # Agent execution limits (per-role max_execution_time in seconds)
    AGENT_MAX_EXECUTION_TIME_DEFAULT: int = 600  # 10 min fallback
    AGENT_MAX_EXECUTION_TIME_RESEARCHER: int = 2400  # 40 min (investigation needs many deep-research calls)
    AGENT_MAX_EXECUTION_TIME_DEVELOPER: int = 1200  # 20 min (code gen can be complex)
    AGENT_MAX_EXECUTION_TIME_CODE_REVIEWER: int = 300  # 5 min (review is read-heavy)
    AGENT_MAX_EXECUTION_TIME_TEAM_LEAD: int = 1200  # 20 min (planning is complex)
    AGENT_MAX_EXECUTION_TIME_PROJECT_LEAD: int = 1800  # 30 min (waits for user responses)
    AGENT_MAX_EXECUTION_TIME_RESEARCH_REVIEWER: int = 300  # 5 min
    CREW_MAX_RPM: int = 30  # LLM API requests per minute across all agents in a crew

    # Agent loop shutdown
    WORKER_SHUTDOWN_TIMEOUT: float = 10.0

    # Semantic dedup (epics, milestones, tasks)
    DEDUP_SIMILARITY_THRESHOLD: float = 0.82

    # Incremental planning limits
    MAX_ACTIVE_EPICS: int = 2           # Max open epics before tools reject new ones
    MAX_MILESTONES_PER_EPIC: int = 4    # Max milestones per epic
    MAX_TASKS_PER_MILESTONE: int = 8    # Max tasks per milestone

    # Agent Engine
    AGENT_ENGINE: str = "crewai"  # "crewai" | "claude_code"
    CLAUDE_CODE_MODEL: str = "claude-opus-4-6"
    CLAUDE_CODE_TIMEOUT_DEFAULT: int = 1800  # 30 min
    CLAUDE_CODE_TIMEOUT_DEVELOPER: int = 3600  # 60 min
    CLAUDE_CODE_TIMEOUT_CODE_REVIEWER: int = 900  # 15 min
    CLAUDE_CODE_TIMEOUT_RESEARCHER: int = 2400  # 40 min
    CLAUDE_CODE_TIMEOUT_TEAM_LEAD: int = 1800  # 30 min
    CLAUDE_CODE_TIMEOUT_PROJECT_LEAD: int = 1800  # 30 min
    CLAUDE_CODE_CREDENTIALS_PATH: str = "~/.claude/.credentials.json"

    # Agent Autonomy Layer
    AUTONOMY_ENABLED: bool = True

    # Per-role toggles
    AUTONOMY_ENABLE_DEVELOPER: bool = True
    AUTONOMY_ENABLE_RESEARCHER: bool = True
    AUTONOMY_ENABLE_TEAM_LEAD: bool = True
    AUTONOMY_ENABLE_PROJECT_LEAD: bool = True

    # Agent Loop settings (unified event-driven loop per agent)
    AGENT_LOOP_POLL_INTERVAL: float = 30.0      # base poll interval (seconds)
    AGENT_LOOP_MAX_IDLE_INTERVAL: float = 300.0  # max backoff when idle (5 min)
    AGENT_LOOP_MAX_ACTIONS_PER_HOUR: int = 20    # per-agent action budget
    AGENT_LOOP_ERROR_THRESHOLD: int = 5          # consecutive errors → stop loop
    AGENT_LOOP_SCAVENGE_AFTER_IDLES: int = 3    # idle polls before scavenging orphan tasks

    model_config = {"env_prefix": "PABADA_"}


settings = Settings()
