"""Minimal DB access for the autonomy package.

This avoids the circular import chain by importing the db module directly
via importlib, bypassing backend/tools/__init__.py.
"""

from __future__ import annotations

import importlib
import sqlite3
from typing import TypeVar

T = TypeVar("T")

_db_mod = None


def _load_db_mod():
    """Load backend.tools.base.db without triggering backend.tools.__init__."""
    global _db_mod
    if _db_mod is not None:
        return _db_mod

    # Import the leaf module directly, bypassing the parent __init__.py
    # by importing the sub-packages first in isolation.
    import importlib.util
    import sys
    from pathlib import Path

    # Find the actual file path
    base_dir = Path(__file__).resolve().parent.parent / "tools" / "base"
    db_file = base_dir / "db.py"

    if "backend.tools.base.db" in sys.modules:
        _db_mod = sys.modules["backend.tools.base.db"]
        return _db_mod

    # Ensure parent package stubs exist in sys.modules so the import doesn't
    # trigger __init__.py chains. We only need the base sub-package.
    for pkg_name in ("backend.tools.base",):
        if pkg_name not in sys.modules:
            import types
            pkg = types.ModuleType(pkg_name)
            pkg.__path__ = [str(base_dir)]
            pkg.__package__ = pkg_name
            sys.modules[pkg_name] = pkg

    spec = importlib.util.spec_from_file_location(
        "backend.tools.base.db", str(db_file),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["backend.tools.base.db"] = mod
    spec.loader.exec_module(mod)

    _db_mod = mod
    return _db_mod


def execute_with_retry(fn, db_path=None, max_retries=None, base_delay=None):
    """Proxy to backend.tools.base.db.execute_with_retry, loaded lazily."""
    mod = _load_db_mod()
    return mod.execute_with_retry(fn, db_path, max_retries, base_delay)


def get_connection(db_path=None):
    """Proxy to backend.tools.base.db.get_connection, loaded lazily."""
    mod = _load_db_mod()
    return mod.get_connection(db_path)
