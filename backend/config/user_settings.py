"""User settings management — .researcher/settings.json"""
import json
import os
from pathlib import Path

RESEARCHER_HOME = Path(os.getcwd()) / ".researcher"
SETTINGS_FILE = RESEARCHER_HOME / "settings.json"

def ensure_researcher_home():
    """Create .researcher/ directory structure on first run."""
    RESEARCHER_HOME.mkdir(exist_ok=True)
    (RESEARCHER_HOME / "logs").mkdir(exist_ok=True)
    (RESEARCHER_HOME / "cache").mkdir(exist_ok=True)

def load_user_settings() -> dict:
    """Load settings from .researcher/settings.json."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

def save_user_settings(updates: dict) -> None:
    """Update .researcher/settings.json with new values."""
    ensure_researcher_home()
    current = load_user_settings()
    current.update(updates)
    SETTINGS_FILE.write_text(json.dumps(current, indent=2) + "\n")

def reload_all() -> None:
    """Reload settings and update the global instance."""
    from backend.config.settings import settings
    user = load_user_settings()
    for key, value in user.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
