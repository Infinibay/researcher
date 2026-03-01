"""Centralized LLM configuration for PABADA.

Single source of truth: reads from ``settings.LLM_MODEL``, ``settings.LLM_API_KEY``,
and ``settings.LLM_BASE_URL``.  Creates a ``crewai.LLM`` singleton used by all agents,
and exposes helpers for direct litellm callers and env-var setup.
"""

from __future__ import annotations

import copy
import functools
import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

# Providers where LiteLLM already knows the API endpoint.
# Do NOT pass base_url for these — it breaks tool parameter routing.
_LITELLM_NATIVE_PROVIDERS = frozenset({"deepseek", "anthropic", "gemini", "openai", "zai"})

# Map provider prefix → env var that LiteLLM expects for the API key.
_PROVIDER_KEY_ENV: dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "zai": "ZAI_API_KEY",
}

_lock = threading.Lock()
_cached_llm: Any | None = None


def _extract_provider(model: str) -> str:
    """Extract provider prefix from a LiteLLM model string.

    ``"deepseek/deepseek-chat"`` → ``"deepseek"``
    ``"gpt-4.1-mini"``          → ``"openai"``   (no prefix = OpenAI)
    ``"qwen3-coder:30b"``       → ``""``          (bare model, e.g. Ollama)
    """
    if "/" in model:
        return model.split("/", 1)[0].lower()
    # No prefix: if it looks like an OpenAI model, treat as openai
    if model.startswith(("gpt-", "o1-", "o3-", "o4-")):
        return "openai"
    return ""


def _is_native_provider(model: str) -> bool:
    """Return True if LiteLLM handles this provider's endpoint natively."""
    return _extract_provider(model) in _LITELLM_NATIVE_PROVIDERS


def get_llm() -> Any:
    """Return a thread-safe singleton ``crewai.LLM`` instance.

    Reads from settings on first call; subsequent calls return the cached object.
    """
    global _cached_llm
    if _cached_llm is not None:
        return _cached_llm

    with _lock:
        # Double-check after acquiring lock
        if _cached_llm is not None:
            return _cached_llm

        from crewai import LLM
        from backend.config.settings import settings

        model = settings.LLM_MODEL
        if not model:
            raise RuntimeError(
                "PABADA_LLM_MODEL is not set. "
                "Set it in .env or as an environment variable."
            )

        kwargs: dict[str, Any] = {"model": model}

        if settings.LLM_API_KEY:
            kwargs["api_key"] = settings.LLM_API_KEY

        # Only pass base_url for non-native providers (e.g. Ollama, vLLM)
        if settings.LLM_BASE_URL and not _is_native_provider(model):
            kwargs["base_url"] = settings.LLM_BASE_URL

        _cached_llm = LLM(**kwargs)

        # Install diagnostic callbacks to detect empty/blocked LLM responses
        _install_llm_diagnostics()

        # Thinking mode control (Qwen3, etc.)
        # CrewAI's OpenAICompletion only passes reasoning_effort for O1
        # models, so we inject it into additional_params directly.
        # LiteLLM maps reasoning_effort to Ollama's `think` parameter:
        #   "none" → think=False,  "low"/"medium"/"high" → think=True
        if not settings.LLM_THINKING:
            _cached_llm.additional_params["reasoning_effort"] = "none"
            logger.info("LLM thinking mode disabled (reasoning_effort=none)")
        logger.info(
            "LLM configured: model=%s, base_url=%s, api_key=%s, thinking=%s",
            model,
            kwargs.get("base_url", "(LiteLLM default)"),
            "set" if settings.LLM_API_KEY else "NOT SET",
            settings.LLM_THINKING,
        )
        return _cached_llm


_diagnostics_installed = False


def _install_llm_diagnostics() -> None:
    """Install litellm callbacks to log empty/blocked responses.

    Helps diagnose why CrewAI throws "Invalid response from LLM call - None or empty".
    Possible causes: safety filters, context overflow, rate limiting.
    """
    global _diagnostics_installed
    if _diagnostics_installed:
        return
    _diagnostics_installed = True

    try:
        import litellm

        _orig_completion = litellm.completion

        @functools.wraps(_orig_completion)
        def _diagnostic_completion(*args: Any, **kwargs: Any) -> Any:
            try:
                result = _orig_completion(*args, **kwargs)
            except Exception as exc:
                logger.warning(
                    "LLM call EXCEPTION: %s | model=%s | messages=%d",
                    str(exc)[:200],
                    kwargs.get("model", "?"),
                    len(kwargs.get("messages", [])),
                )
                raise

            # Check for empty/blocked response
            if result is None:
                logger.warning("LLM returned None (possible safety filter or timeout)")
            elif hasattr(result, "choices") and result.choices:
                choice = result.choices[0]
                content = getattr(choice.message, "content", None) or ""
                finish = getattr(choice, "finish_reason", "unknown")
                if not content.strip() and finish != "tool_calls":
                    logger.warning(
                        "LLM returned EMPTY content | finish_reason=%s | model=%s | "
                        "prompt_tokens=%s | completion_tokens=%s",
                        finish,
                        getattr(result, "model", "?"),
                        getattr(getattr(result, "usage", None), "prompt_tokens", "?"),
                        getattr(getattr(result, "usage", None), "completion_tokens", "?"),
                    )
            return result

        litellm.completion = _diagnostic_completion
        logger.info("Installed LLM diagnostic wrapper")
    except Exception:
        logger.debug("Could not install LLM diagnostics", exc_info=True)


def get_litellm_params() -> dict[str, Any]:
    """Return kwargs suitable for ``litellm.completion(**params, messages=...)``.

    Used by callers that invoke litellm directly (e.g. deep_research.py).
    """
    from backend.config.settings import settings

    model = settings.LLM_MODEL
    if not model:
        raise RuntimeError("PABADA_LLM_MODEL is not set.")

    params: dict[str, Any] = {"model": model}

    if settings.LLM_API_KEY:
        params["api_key"] = settings.LLM_API_KEY

    if settings.LLM_BASE_URL and not _is_native_provider(model):
        params["api_base"] = settings.LLM_BASE_URL

    return params


def validate_function_calling() -> None:
    """Check if the configured model supports function calling and warn if not.

    PABADA agents require tool/function calling to operate — without it,
    agents respond with text but never invoke tools.
    """
    from backend.config.settings import settings

    model = settings.LLM_MODEL
    if not model:
        return

    try:
        import litellm
        supports_fc = litellm.utils.supports_function_calling(model)
        if supports_fc:
            logger.info("LLM model '%s' supports function calling", model)
        else:
            logger.warning(
                "LLM model '%s' does NOT support function calling! "
                "PABADA agents will be unable to use tools (read files, "
                "create tasks, search code, etc.). "
                "Consider switching to a model that supports function calling "
                "(e.g., deepseek/deepseek-chat, gemini/gemini-2.0-flash, "
                "gpt-4.1-mini, anthropic/claude-sonnet-4-5-20250929).",
                model,
            )
    except Exception as exc:
        logger.debug("Could not check function calling support: %s", exc)


def setup_provider_env_vars() -> None:
    """Set the minimal env vars that LiteLLM needs internally.

    - ``OPENAI_API_KEY`` fallback (LiteLLM reads it for several providers)
    - Provider-specific key (e.g. ``GEMINI_API_KEY``)
    - Installs tool-schema sanitizer for providers that need it (DeepSeek)
    """
    from backend.config.settings import settings

    if settings.LLM_API_KEY:
        os.environ.setdefault("OPENAI_API_KEY", settings.LLM_API_KEY)

        provider = _extract_provider(settings.LLM_MODEL)
        env_var = _PROVIDER_KEY_ENV.get(provider)
        if env_var:
            os.environ.setdefault(env_var, settings.LLM_API_KEY)
    elif not os.environ.get("OPENAI_API_KEY"):
        # For Ollama/local providers without an API key, set a dummy
        # OPENAI_API_KEY so third-party code that reads it (e.g. OpenAI
        # client constructors) doesn't crash during import.
        os.environ["OPENAI_API_KEY"] = "not-needed"

    # Export third-party tool API keys
    if settings.SERPER_API_KEY:
        os.environ.setdefault("SERPER_API_KEY", settings.SERPER_API_KEY)
    if settings.SPIDER_API_KEY:
        os.environ.setdefault("SPIDER_API_KEY", settings.SPIDER_API_KEY)

    # DeepSeek rejects anyOf in tool parameter schemas (Pydantic v2 generates
    # these for Optional fields).  Install a one-time patch.
    if _extract_provider(settings.LLM_MODEL) == "deepseek":
        _install_schema_fix()


# ---------------------------------------------------------------------------
# Tool-schema sanitizer for providers with strict JSON Schema validation
# ---------------------------------------------------------------------------

def _sanitize_schema(schema: dict) -> dict:
    """Recursively simplify JSON Schema to remove ``anyOf`` / ``allOf``.

    Pydantic v2 emits ``{"anyOf": [{"type": "string"}, {"type": "null"}]}``
    for ``Optional[str]``.  DeepSeek's API rejects ``anyOf`` as a map.  This
    function flattens such patterns to ``{"type": "string"}``.
    """
    if not isinstance(schema, dict):
        return schema

    any_of = schema.get("anyOf")
    all_of = schema.get("allOf")

    # First pass: copy all keys except anyOf / allOf (recurse into children)
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key in ("anyOf", "allOf"):
            continue
        if key in ("properties", "$defs", "definitions") and isinstance(value, dict):
            result[key] = {k: _sanitize_schema(v) for k, v in value.items()}
        elif key == "items" and isinstance(value, dict):
            result[key] = _sanitize_schema(value)
        elif isinstance(value, dict):
            result[key] = _sanitize_schema(value)
        elif isinstance(value, list):
            result[key] = [_sanitize_schema(v) if isinstance(v, dict) else v for v in value]
        else:
            result[key] = value

    # Flatten anyOf → pick the first non-null type
    if any_of and isinstance(any_of, list):
        non_null = [
            v for v in any_of
            if not (isinstance(v, dict) and v.get("type") == "null")
        ]
        chosen = non_null[0] if non_null else any_of[0]
        for mk, mv in _sanitize_schema(chosen).items():
            result.setdefault(mk, mv)

    # Flatten single-item allOf (Pydantic uses this for $ref wrappers)
    if all_of and isinstance(all_of, list) and len(all_of) == 1:
        for mk, mv in _sanitize_schema(all_of[0]).items():
            result.setdefault(mk, mv)

    return result


_schema_fix_installed = False


def _install_schema_fix() -> None:
    """Monkey-patch ``litellm.completion`` / ``acompletion`` to sanitize tool schemas.

    Required for DeepSeek which rejects ``anyOf`` in tool parameter schemas.
    Idempotent — only patches once.
    """
    global _schema_fix_installed
    if _schema_fix_installed:
        return
    _schema_fix_installed = True

    import litellm

    _orig = litellm.completion
    _aorig = litellm.acompletion

    def _sanitize_tools(kwargs: dict) -> None:
        tools = kwargs.get("tools")
        if not tools:
            return
        sanitized = []
        for tool in tools:
            if isinstance(tool, dict) and "function" in tool:
                tool = copy.deepcopy(tool)
                params = tool["function"].get("parameters")
                if params:
                    tool["function"]["parameters"] = _sanitize_schema(params)
            sanitized.append(tool)
        kwargs["tools"] = sanitized

    @functools.wraps(_orig)
    def _patched_completion(*args, **kwargs):
        _sanitize_tools(kwargs)
        return _orig(*args, **kwargs)

    @functools.wraps(_aorig)
    async def _patched_acompletion(*args, **kwargs):
        _sanitize_tools(kwargs)
        return await _aorig(*args, **kwargs)

    litellm.completion = _patched_completion
    litellm.acompletion = _patched_acompletion
    logger.info("Installed tool-schema sanitizer (anyOf → simple types)")


def _reset_llm_cache() -> None:
    """Clear the cached LLM singleton. For tests only."""
    global _cached_llm
    with _lock:
        _cached_llm = None
