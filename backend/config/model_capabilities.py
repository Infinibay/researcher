"""Unknown legacy capability metadata remains readable; retired provider probes cannot establish or guess native account/model support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ModelCapabilities:
    """Historical capability fields default to unknown; only explicit source evidence could describe an old observation, never live native support."""

    supports_function_calling: bool | None = None
    supports_tool_choice_required: bool | None = None
    supports_json_mode: bool | None = None
    has_thinking_sections: bool | None = None
    needs_schema_sanitization: bool | None = None
    probed: bool = False
    probe_duration: float = 0.0


_capabilities = ModelCapabilities()


def get_model_capabilities() -> ModelCapabilities:
    """Read unobserved legacy metadata; native capability preflight stays in the actual admitted runtime protocol."""
    return _capabilities


def probe_model(llm_params: dict[str, Any]) -> ModelCapabilities:
    """Reject old synthetic generation probes before provider import or any paid request; a retired probe never reports success."""
    from backend.runtime.lifecycle import NativeOwnerRequired

    raise NativeOwnerRequired("Legacy model probing is retired; inspect the configured native runtime's actual capability result")


def _run_probes(llm_params: dict[str, Any]) -> ModelCapabilities:
    """Retain the historical private entry without a backdoor to the old provider probes."""
    return probe_model(llm_params)


def _reset_capabilities() -> None:
    """Reset historical metadata to explicitly unobserved support, not optimistic defaults."""
    global _capabilities
    _capabilities = ModelCapabilities()
