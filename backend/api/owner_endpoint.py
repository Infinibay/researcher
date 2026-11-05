"""Bind paired owner clients to the actual canonical database identity without exposing filesystem paths or model credentials."""

import hashlib
import json
from pathlib import Path


def endpoint_identity(request):
    """Return installation plus physical database identity; a replacement/clone must not silently inherit a pending client's authority."""
    from backend.api.routes.runs import read_store

    runs = read_store(request)
    path = Path(runs.database).resolve(strict=True)
    before = path.stat()
    with runs._transaction() as conn:
        installation = conn.execute(
            "SELECT installation_id FROM runtime_owner_endpoint WHERE singleton=1"
        ).fetchone()[0]
    after = path.stat()
    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
        raise RuntimeError(
            "Owner database changed while inspecting its endpoint identity"
        )
    return hashlib.sha256(
        json.dumps(
            [installation, before.st_dev, before.st_ino], separators=(",", ":")
        ).encode()
    ).hexdigest()


def endpoint_scope(request):
    """Attest actual host workspace roots for private terminal state checks; a client's cwd is not evidence of server source ownership."""
    from backend.api.routes.runs import read_store

    runtime = request.app.state.runtime_service
    if runtime is not None:
        roots = [str(runtime.workspaces.root)]
    else:
        with read_store(request)._transaction() as conn:
            roots = sorted(
                {
                    str(Path(row[0]).resolve())
                    for row in conn.execute(
                        "SELECT local_path FROM repositories WHERE status='active' AND local_path IS NOT NULL"
                    )
                    if row[0]
                }
            )
    return {"endpoint_id": endpoint_identity(request), "workspace_roots": roots}
