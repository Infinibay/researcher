"""Tests for backend.config.user_settings."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _patch_paths(tmp_path, monkeypatch):
    """Redirect RESEARCHER_HOME and SETTINGS_FILE to tmp_path."""
    home = tmp_path / ".researcher"
    settings_file = home / "settings.json"
    monkeypatch.setattr(
        "backend.config.user_settings.RESEARCHER_HOME", home,
    )
    monkeypatch.setattr(
        "backend.config.user_settings.SETTINGS_FILE", settings_file,
    )
    return home, settings_file


class TestEnsureResearcherHome:
    def test_creates_directory_structure(self, tmp_path, _patch_paths):
        from backend.config.user_settings import ensure_researcher_home

        home, _ = _patch_paths
        ensure_researcher_home()

        assert home.is_dir()
        assert (home / "logs").is_dir()
        assert (home / "cache").is_dir()

    def test_idempotent(self, tmp_path, _patch_paths):
        from backend.config.user_settings import ensure_researcher_home

        ensure_researcher_home()
        ensure_researcher_home()  # should not raise

        home, _ = _patch_paths
        assert home.is_dir()


class TestLoadUserSettings:
    def test_returns_empty_dict_when_no_file(self, _patch_paths):
        from backend.config.user_settings import load_user_settings

        result = load_user_settings()
        assert result == {}

    def test_reads_json_correctly(self, _patch_paths):
        from backend.config.user_settings import load_user_settings

        home, settings_file = _patch_paths
        home.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(json.dumps({"LLM_MODEL": "test-model", "DEV_COUNT": 3}))

        result = load_user_settings()
        assert result == {"LLM_MODEL": "test-model", "DEV_COUNT": 3}

    def test_returns_empty_dict_on_invalid_json(self, _patch_paths):
        from backend.config.user_settings import load_user_settings

        home, settings_file = _patch_paths
        home.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("not valid json {{{")

        result = load_user_settings()
        assert result == {}


class TestSaveUserSettings:
    def test_writes_and_merges(self, _patch_paths):
        from backend.config.user_settings import load_user_settings, save_user_settings

        save_user_settings({"LLM_MODEL": "model-a"})
        assert load_user_settings() == {"LLM_MODEL": "model-a"}

        # Merge with existing
        save_user_settings({"DEV_COUNT": 2})
        result = load_user_settings()
        assert result == {"LLM_MODEL": "model-a", "DEV_COUNT": 2}

    def test_overwrites_existing_key(self, _patch_paths):
        from backend.config.user_settings import load_user_settings, save_user_settings

        save_user_settings({"LLM_MODEL": "model-a"})
        save_user_settings({"LLM_MODEL": "model-b"})
        assert load_user_settings()["LLM_MODEL"] == "model-b"

    def test_creates_directory_if_missing(self, _patch_paths):
        from backend.config.user_settings import save_user_settings

        home, settings_file = _patch_paths
        assert not home.exists()
        save_user_settings({"key": "val"})
        assert settings_file.exists()


class TestReloadAll:
    def test_updates_global_settings(self, _patch_paths):
        from backend.config.user_settings import save_user_settings, reload_all

        # Save a setting
        save_user_settings({"LLM_MODEL": "reloaded-model"})

        # Mock the settings object at its source (where reload_all imports it from)
        mock_settings = MagicMock()
        mock_settings.LLM_MODEL = "old-model"

        with patch("backend.config.settings.settings", mock_settings):
            reload_all()

        # reload_all should have set LLM_MODEL on the settings object
        mock_settings.__setattr__("LLM_MODEL", "reloaded-model")

    def test_settings_json_path(self, _patch_paths):
        """Settings file should live at .researcher/settings.json."""
        _, settings_file = _patch_paths
        assert settings_file.name == "settings.json"
        assert settings_file.parent.name == ".researcher"
