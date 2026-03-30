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
    from backend.config.settings import settings
    ensure_researcher_home()
    current = load_user_settings()
    for key, value in updates.items():
        current[key] = _coerce_value(settings, key, value) if hasattr(settings, key) else value
    SETTINGS_FILE.write_text(json.dumps(current, indent=2) + "\n")

def _coerce_value(settings_obj: object, key: str, value: object) -> object:
    """Coerce a JSON value to match the type of the existing setting."""
    current = getattr(settings_obj, key, None)
    if current is None:
        return value
    if isinstance(current, bool):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    if isinstance(current, int) and not isinstance(value, int):
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return current
    if isinstance(current, float) and not isinstance(value, float):
        try:
            return float(str(value))
        except (ValueError, TypeError):
            return current
    if isinstance(current, list) and isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def reload_all() -> None:
    """Reload settings and update the global instance."""
    from backend.config.settings import settings
    user = load_user_settings()
    for key, value in user.items():
        if hasattr(settings, key):
            setattr(settings, key, _coerce_value(settings, key, value))
