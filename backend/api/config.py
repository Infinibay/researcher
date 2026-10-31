"""API-specific configuration extending the base INFINIBAY settings."""

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# API defaults
API_HOST: str = "127.0.0.1"
API_PORT: int = 8000
API_RELOAD: bool = True
CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
]
STATIC_DIR: str = "frontend/dist"
UPLOAD_DIR: str = str(_PROJECT_ROOT / ".data" / "uploads")
