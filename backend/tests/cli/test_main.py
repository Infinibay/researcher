"""Tests for backend.cli.main command handlers."""

from unittest.mock import MagicMock, patch

import pytest

from backend.cli.main import _handle_command, _handle_models, _handle_settings


class TestHandleCommand:
    def test_help_returns_help_text(self):
        result = _handle_command("/help")
        assert result is not None
        assert "Commands:" in result
        assert "/settings" in result
        assert "/exit" in result

    def test_exit_returns_sentinel(self):
        assert _handle_command("/exit") == "__EXIT__"

    def test_quit_returns_sentinel(self):
        assert _handle_command("/quit") == "__EXIT__"

    def test_q_returns_sentinel(self):
        assert _handle_command("/q") == "__EXIT__"

    def test_unknown_returns_none(self):
        result = _handle_command("hello world")
        assert result is None

    def test_non_command_returns_none(self):
        result = _handle_command("fix the bug in main.py")
        assert result is None

    def test_settings_delegates(self):
        with patch("backend.cli.main._handle_settings") as mock_settings:
            mock_settings.return_value = "settings output"
            result = _handle_command("/settings")
            mock_settings.assert_called_once()

    def test_models_delegates(self):
        with patch("backend.cli.main._handle_models") as mock_models:
            mock_models.return_value = "models output"
            result = _handle_command("/models")
            mock_models.assert_called_once()


class TestHandleSettings:
    def test_show_all_settings(self):
        mock_settings = MagicMock()
        mock_settings.LLM_MODEL = "test-model"
        mock_settings.LLM_BASE_URL = "http://localhost"
        mock_settings.MULTI_DEV_ENABLED = False
        mock_settings.CODE_INTEL_ENABLED = True
        mock_settings.REVIEW_ENABLED = True
        mock_settings.ANALYSIS_ENABLED = True

        with patch("backend.config.settings.settings", mock_settings):
            with patch("backend.config.user_settings.load_user_settings", return_value={}):
                result = _handle_settings("/settings")
        assert "Current settings" in result

    def test_set_value(self):
        mock_settings = MagicMock()
        mock_settings.LLM_MODEL = "old-model"

        with patch("backend.config.settings.settings", mock_settings):
            with patch("backend.config.user_settings.save_user_settings") as mock_save:
                result = _handle_settings("/settings LLM_MODEL new-model")
        assert "Set LLM_MODEL" in result
        mock_save.assert_called_once()

    def test_show_single_setting(self):
        mock_settings = MagicMock()
        mock_settings.LLM_MODEL = "my-model"

        with patch("backend.config.settings.settings", mock_settings):
            result = _handle_settings("/settings LLM_MODEL")
        assert "LLM_MODEL" in result
        assert "my-model" in result

    def test_unknown_setting(self):
        mock_settings = MagicMock(spec=[])  # spec=[] means no attributes

        with patch("backend.config.settings.settings", mock_settings):
            result = _handle_settings("/settings NONEXISTENT_SETTING")
        assert "Unknown setting" in result


class TestHandleModels:
    def test_shows_current_model(self):
        mock_settings = MagicMock()
        mock_settings.LLM_MODEL = "qwen3-coder:30b"

        with patch("backend.config.settings.settings", mock_settings):
            result = _handle_models("/models")
        assert "qwen3-coder:30b" in result

    def test_switches_model(self):
        mock_settings = MagicMock()

        with patch("backend.config.settings.settings", mock_settings):
            with patch("backend.config.user_settings.save_user_settings") as mock_save:
                result = _handle_models("/models gemini/gemini-2.0-flash")
        assert "gemini/gemini-2.0-flash" in result
        mock_save.assert_called_once_with({"LLM_MODEL": "gemini/gemini-2.0-flash"})
