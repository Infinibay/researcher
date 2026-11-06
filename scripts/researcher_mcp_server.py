#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp==1.30.0", "httpx==0.28.1", "pydantic==2.14.2"]
# ///
"""Compatibility launch name for the packaged scoped business MCP; host grant is required and old project/actor environment labels confer no authority."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.research.stdio_server import main


if __name__ == '__main__':
    raise SystemExit(main())
