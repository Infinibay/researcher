"""Resolve API assets and writable attachment storage once at process startup.

INFINIBAY_UPLOAD_BASE_DIR selects existing attachment storage explicitly.
Otherwise uploads live below INFINIBAY_DATA, or the working directory's .data.
Reading configuration never creates directories or relocates existing files.
"""

import os
from pathlib import Path

# API defaults
API_HOST: str = "127.0.0.1"
API_PORT: int = 8000
API_RELOAD: bool = True
CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]
STATIC_DIR: str = str(
    Path(os.environ.get("INFINIBAY_STATIC_DIR", "frontend/dist")).expanduser().resolve()
)
UPLOAD_DIR: str = str(
    Path(
        os.environ.get(
            "INFINIBAY_UPLOAD_BASE_DIR",
            str(Path(os.environ.get("INFINIBAY_DATA", ".data")) / "uploads"),
        )
    ).expanduser().resolve()
)
