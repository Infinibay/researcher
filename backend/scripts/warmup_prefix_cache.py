"""Retired direct-provider warmup entry: native sessions own caching and no historical role prompt may trigger standalone inference."""

import sys


def _warmup_one(role,prompt,base_url,model):
    """Reject historical direct calls before HTTP, provider selection or prompt rendering; compatibility does not authorize a one-token completion."""
    from backend.runtime.lifecycle import NativeOwnerRequired

    raise NativeOwnerRequired('Direct prompt warmup is retired; use the owned Codex subscription runtime.')


def main():
    """Explain retirement without probing a server, importing role builders, reading credentials or sending a model request."""
    print('Direct prompt warmup is retired. Use the owned Codex subscription runtime; no request was sent.',file=sys.stderr)
    return 2


if __name__=='__main__':
    raise SystemExit(main())
