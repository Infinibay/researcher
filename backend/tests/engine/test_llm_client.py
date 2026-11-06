"""Tests for backend.engine.llm_client."""


import pytest

from backend.engine.llm_client import (
    is_malformed_tool_call,
    is_transient,
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


class TestRetiredCallLlm:
    """Historical pure classifiers remain available; direct generation no longer owns retries or provider calls."""

    def test_old_call_requires_native_admission(self):
        """Provider parameters cannot authorize a call through the retired client."""
        from backend.engine.llm_client import call_llm
        from backend.runtime.lifecycle import NativeOwnerRequired

        with pytest.raises(NativeOwnerRequired):
            call_llm({"model":"old-provider"},[{"role":"user","content":"old request"}])
