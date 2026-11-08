"""Serve the installed coordinator with only its native transport replaced by a frozen non-generative fixture."""

import argparse
import hashlib
import os
import sys
from dataclasses import replace
from pathlib import Path


def main():
    """Preserve the product authority, command ownership, Ken and HTTP paths in an isolated evaluation service."""
    import backend

    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('Use installed product Python with -I')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--asset', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    if hashlib.sha256(args.asset.read_bytes()).hexdigest() != args.sha256:
        raise ValueError('Registered controlled transport changed')
    from backend.runtime.host_installation import host_environment

    os.environ.update(host_environment(args.installation))
    import uvicorn
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.runtime.broker_profile import CodexAsset

    app = create_app()
    coordinator = configured_runtime(app.state.live_grants, app=app)
    coordinator.runtime = replace(coordinator.runtime, asset=CodexAsset.inspect(args.asset))
    app.state.runtime_service = coordinator
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning', access_log=False)


if __name__ == '__main__':
    main()
