"""Tests for backend.engine.llm_client."""

from unittest.mock import MagicMock, patch

import pytest

from backend.engine.llm_client import (
    is_malformed_tool_call,
    is_transient,
    call_llm,
    LLM_RETRIES,
)


class TestIsTransient:
    def test_connection_error_is_transient(self):
        assert is_transient(Exception("Connection error while calling API")) is True

    def test_timeout_is_transient(self):
        assert is_transient(Exception("Request timeout after 30s")) is True

    def test_rate_limit_is_transient(self):
        assert is_transient(Exception("rate limit exceeded")) is True

    def test_503_is_transient(self):
        assert is_transient(Exception("HTTP 503 Service Unavailable")) is True

    def test_429_is_transient(self):
        assert is_transient(Exception("429 Too Many Requests")) is True

    def test_unknown_error_not_transient(self):
        assert is_transient(Exception("something unexpected")) is False

    def test_permanent_overrides_transient(self):
        # "does not support tools" should override even if "503" is present
        assert is_transient(Exception("does not support tools")) is False

    def test_not_found_is_permanent(self):
        assert is_transient(Exception("model not found")) is False

    def test_tool_choice_not_supported_is_permanent(self):
        assert is_transient(Exception("tool_choice is not supported")) is False


class TestIsMalformedToolCall:
    def test_detects_invalid_json(self):
        assert is_malformed_tool_call(Exception("invalid json in response")) is True

    def test_detects_parse_error(self):
        assert is_malformed_tool_call(Exception("Error parsing tool call")) is True

    def test_detects_unterminated_string(self):
        assert is_malformed_tool_call(Exception("unterminated string in JSON")) is True

    def test_normal_error_not_malformed(self):
        assert is_malformed_tool_call(Exception("connection error")) is False


class TestCallLlm:
    @patch("backend.config.model_capabilities.get_model_capabilities")
    @patch("litellm.completion")
    def test_retries_on_transient_error(self, mock_completion, mock_caps):
        mock_caps.return_value = MagicMock(
            supports_tool_choice_required=True,
            has_thinking_sections=False,
            supports_json_mode=False,
        )

        # Fail twice with transient error, then succeed
        mock_completion.side_effect = [
            Exception("connection error"),
            Exception("timeout"),
            MagicMock(choices=[MagicMock()]),
        ]

        with patch("backend.engine.llm_client.time.sleep"):  # Don't actually sleep
            result = call_llm(
                params={"model": "test"},
                messages=[{"role": "user", "content": "hello"}],
            )

        assert mock_completion.call_count == 3

    @patch("backend.config.model_capabilities.get_model_capabilities")
    @patch("litellm.completion")
    def test_raises_on_permanent_error(self, mock_completion, mock_caps):
        mock_caps.return_value = MagicMock(
            supports_tool_choice_required=True,
            has_thinking_sections=False,
            supports_json_mode=False,
        )

        mock_completion.side_effect = Exception("does not support tools")

        with pytest.raises(Exception, match="does not support tools"):
            call_llm(
                params={"model": "test"},
                messages=[{"role": "user", "content": "hello"}],
            )

        # Should not retry permanent errors
        assert mock_completion.call_count == 1

    @patch("backend.config.model_capabilities.get_model_capabilities")
    @patch("litellm.completion")
    def test_raises_after_max_retries(self, mock_completion, mock_caps):
        mock_caps.return_value = MagicMock(
            supports_tool_choice_required=True,
            has_thinking_sections=False,
            supports_json_mode=False,
        )

        mock_completion.side_effect = Exception("connection error")

        with patch("backend.engine.llm_client.time.sleep"):
            with pytest.raises(Exception, match="connection error"):
                call_llm(
                    params={"model": "test"},
                    messages=[{"role": "user", "content": "hello"}],
                )

        assert mock_completion.call_count == LLM_RETRIES
