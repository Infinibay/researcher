"""Development server entry point for the PABADA API."""

import logging
import os
import warnings
from pathlib import Path

import uvicorn

# Suppress ONNX Runtime warnings (chromadb dependency) that use warnings.warn
warnings.filterwarnings("ignore", category=UserWarning, module="onnxruntime")
warnings.filterwarnings("ignore", message=".*ONNX.*")
warnings.filterwarnings("ignore", message=".*onnxruntime.*")


def setup_file_logging():
    """Configure logging to write to .data/pabada.log for debugging."""
    log_dir = Path(os.environ.get("PABADA_DATA", ".data"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pabada.log"

    # File handler with detailed formatting
    file_handler = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # Add to root logger so ALL loggers (backend.*, crewai.*, etc.) write to file
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    # Also ensure backend loggers are at DEBUG level
    logging.getLogger("backend").setLevel(logging.DEBUG)

    # Suppress noisy third-party loggers that flood the log file
    for _noisy in (
        "watchfiles", "httpcore", "httpx", "urllib3", "urllib3.connectionpool",
        "chromadb", "chromadb.config", "chromadb.api",
        "onnxruntime", "onnxruntime.transformers",
    ):
        logging.getLogger(_noisy).setLevel(logging.WARNING)

    # Keep LiteLLM/OpenAI debug logs in the file but out of stdout.
    # LiteLLM prints full prompts at DEBUG level which floods the console.
    for _llm_logger_name in ("LiteLLM", "litellm", "openai", "openai._base_client"):
        _llm_logger = logging.getLogger(_llm_logger_name)
        _llm_logger.setLevel(logging.DEBUG)  # still goes to file handler
        # Remove any inherited stream handlers; add one at WARNING only
        for _h in _llm_logger.handlers[:]:
            _llm_logger.removeHandler(_h)
        _console = logging.StreamHandler()
        _console.setLevel(logging.WARNING)
        _llm_logger.addHandler(_console)
        _llm_logger.propagate = False  # don't bubble to root (stdout)

    logging.getLogger(__name__).info("File logging enabled → %s", log_file)


def setup_llm_environment():
    """Configure the centralized LLM singleton and provider env vars.

    Delegates to ``backend.config.llm`` — the single source of truth for
    all LLM configuration.  Eager-inits the LLM object so errors surface
    at startup rather than on first agent creation.
    """
    from backend.config.llm import setup_provider_env_vars, get_llm, get_litellm_params

    setup_provider_env_vars()

    try:
        get_llm()  # eager init — surface config errors early
    except RuntimeError as exc:
        logging.getLogger(__name__).warning("LLM init skipped: %s", exc)
        return

    # Probe model capabilities (replaces static validate_function_calling)
    try:
        from backend.config.model_capabilities import probe_model

        llm_params = get_litellm_params()
        if llm_params:
            caps = probe_model(llm_params)
            if not caps.supports_function_calling:
                logging.getLogger(__name__).warning(
                    "Model does NOT support function calling — "
                    "LoopEngine will use manual (prompt-based) tool calling."
                )
            # Install schema fix if probe detected the need
            if caps.needs_schema_sanitization:
                from backend.config.llm import _install_schema_fix
                _install_schema_fix()
    except Exception as exc:
        logging.getLogger(__name__).warning("Model probe failed: %s", exc)


def main():
    setup_file_logging()
    setup_llm_environment()

    # Bridge CrewAI internal events into PABADA's EventBus → WebSocket pipeline
    from backend.flows.crewai_event_bridge import register_crewai_event_bridge
    register_crewai_event_bridge()

    # NOTE: No custom signal handlers here — with reload=True, uvicorn runs
    # the ASGI server in a child process while this (parent) process is just
    # the reloader.  The flow_manager lives in the child, so signal handlers
    # here can't reach it.  Graceful shutdown is handled by the FastAPI
    # lifespan handler in main.py (which runs inside the child process).

    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=[".data/*"],
        log_level="info",
    )


if __name__ == "__main__":
    main()
