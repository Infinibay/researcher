#!/usr/bin/env bash
# Start installed local services. Setup is explicit; no .env shell execution,
# provider/container provisioning, package installation or PID files.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
PYTHON="${RESEARCHER_PYTHON:-$SCRIPT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
    if [ -n "${RESEARCHER_PYTHON:-}" ]; then
        echo 'RESEARCHER_PYTHON is not executable; select an installed Python environment.' >&2
        exit 1
    fi
    PYTHON="$(command -v python3)"
fi
exec "$PYTHON" -m backend.cli.launcher "$@"
