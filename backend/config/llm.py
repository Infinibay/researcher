"""Retired provider configuration; native runtime configuration and subscription authentication own every admitted inference call.

Pure historical provider/schema readers remain for migration only. They cannot
construct models, export API keys, probe capabilities or patch installed clients.
"""

from __future__ import annotations

from typing import Any

_LITELLM_NATIVE_PROVIDERS = frozenset({"deepseek", "anthropic", "gemini", "openai", "zai"})


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


def _retired_provider() -> None:
    """Reject before importing a provider or selecting a fallback billing method."""
    from backend.runtime.lifecycle import NativeOwnerRequired

    raise NativeOwnerRequired("Legacy provider configuration is retired; use the configured native runtime and subscription authentication")


def get_llm() -> Any:
    """Reject the old CrewAI model factory before construction; native sessions own actual model selection and authentication."""
    _retired_provider()


def get_litellm_params() -> dict[str, Any] | None:
    """Reject old direct-provider configuration rather than translating ambient API keys into a fallback request."""
    _retired_provider()


def validate_function_calling() -> None:
    """Reject old capability validation; only the original native protocol can establish capability for its selected account/model."""
    _retired_provider()


def setup_provider_env_vars() -> None:
    """Keep the old startup hook inert without exporting credentials or changing the native controller's authentication."""
    return None


def _install_llm_diagnostics() -> None:
    """Keep historical setup calls inert; never monkey-patch another inference client."""
    return None


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



def _install_schema_fix() -> None:
    """Leave actual native schemas untouched; historical simplification is not native protocol validation."""
    return None


def _reset_llm_cache() -> None:
    """Retain the old test/reader hook without constructing or retaining a provider singleton."""
    return None
