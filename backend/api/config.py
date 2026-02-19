"""API-specific configuration extending the base PABADA settings."""

from backend.config.settings import Settings, settings

# API defaults
API_HOST: str = "0.0.0.0"
API_PORT: int = 8000
API_RELOAD: bool = True
CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
]
STATIC_DIR: str = "frontend/dist"
UPLOAD_DIR: str = "/research/projects"
