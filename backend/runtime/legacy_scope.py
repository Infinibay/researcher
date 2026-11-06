"""Correlate a legacy controller's cooperative stop signal with its own execution thread.

This scope conveys cancellation only. It is never native admission, a filesystem
permission, proof of physical closure or authority inferred from a message.
"""

from contextlib import contextmanager
from contextvars import ContextVar

_scope = ContextVar("legacy_controller_stop_scope", default=None)


class LegacyControllerStopped(RuntimeError):
    """Interrupt the retained controller's cooperative call tree without claiming its worker or external effects have physically closed."""


@contextmanager
def legacy_stop_scope(project_id, signal):
    """Bind the owning controller's signal for this call tree and restore any prior scope on exit."""
    if type(project_id) is not int or project_id <= 0:
        raise ValueError("Legacy stop scope requires an explicit project")
    token = _scope.set((project_id, signal))
    try:
        yield
    finally:
        _scope.reset(token)


def check_legacy_stop(project_id):
    """Stop future legacy effects after a request; a mismatched project scope cannot be silently borrowed."""
    bound = _scope.get()
    if bound is None:
        return
    if bound[0] != project_id:
        raise ValueError("Legacy controller/project scope mismatch")
    if bound[1].is_set():
        raise LegacyControllerStopped(
            "Legacy controller requested stop; the returned request does not authorize more work"
        )
