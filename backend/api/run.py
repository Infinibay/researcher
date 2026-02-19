"""Development server entry point for the PABADA API."""

import logging
import os
from pathlib import Path

import uvicorn


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

    logging.getLogger(__name__).info("File logging enabled → %s", log_file)


def setup_llm_environment():
    """Set environment variables for CrewAI's LLM resolution.

    CrewAI reads OPENAI_MODEL_NAME, OPENAI_API_BASE, and OPENAI_API_KEY
    to configure the default LLM for all agents.  We bridge from PABADA
    settings so the user only needs to set PABADA_LLM_MODEL, etc.
    """
    from backend.config.settings import settings

    if settings.LLM_MODEL and not os.environ.get("OPENAI_MODEL_NAME"):
        os.environ["OPENAI_MODEL_NAME"] = settings.LLM_MODEL
        os.environ.setdefault("MODEL", settings.LLM_MODEL)

    if settings.LLM_BASE_URL and not os.environ.get("OPENAI_API_BASE"):
        os.environ["OPENAI_API_BASE"] = settings.LLM_BASE_URL

    if settings.LLM_API_KEY and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = settings.LLM_API_KEY

    logger = logging.getLogger(__name__)
    model = os.environ.get("OPENAI_MODEL_NAME") or os.environ.get("MODEL") or "(default)"
    base = os.environ.get("OPENAI_API_BASE") or "(default)"
    has_key = bool(os.environ.get("OPENAI_API_KEY"))
    logger.info("LLM config: model=%s, base_url=%s, api_key=%s", model, base, "set" if has_key else "NOT SET")


def main():
    setup_file_logging()
    setup_llm_environment()
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
