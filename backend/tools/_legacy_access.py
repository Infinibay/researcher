"""Keep historical tool metadata opt-in without activating legacy frameworks in the native default installation."""

from importlib.metadata import PackageNotFoundError, distribution

LEGACY_DISTRIBUTIONS = ('crewai', 'crewai-tools', 'litellm', 'ollama', 'chromadb')


class LegacyMetadataUnavailable(RuntimeError):
    """An explicitly requested historical reader lacks its optional packages; native execution needs none of them."""


def require_legacy_extra() -> None:
    """Check metadata before importing old frameworks; never install packages, select a provider or mutate native configuration."""
    for name in LEGACY_DISTRIBUTIONS:
        try:
            distribution(name)
        except PackageNotFoundError as error:
            raise LegacyMetadataUnavailable(
                'Historical tool metadata needs the explicit [legacy] extra from this same project version. Native tasks use the scoped business catalogue.'
            ) from error


def load_legacy_tool_base():
    """Load the old class only for a complete explicit historical-reader installation, before any tool is constructed."""
    require_legacy_extra()
    from crewai.tools import BaseTool

    return BaseTool
