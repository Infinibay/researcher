"""Transport-only public-address checks and bounded libc DNS resolution."""

import ipaddress
import json
import os
import subprocess
import sys


class PublicNetworkError(ValueError):
    """Report invalid, nonpublic or unavailable network destination resolution."""
    pass


def public_address(value):
    """Parse a globally routable IP and reject reserved, multicast, scoped and transition-address forms."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        raise PublicNetworkError("DNS returned an invalid address") from None
    if (
        not address.is_global
        or address.is_multicast
        or address.is_reserved
        or isinstance(address, ipaddress.IPv6Address)
        and (
            address.sixtofour is not None
            or address.teredo is not None
            or address.scope_id is not None
        )
    ):
        raise PublicNetworkError("Destination must be a public Internet address")
    return address


def resolve_addresses(host, timeout):
    """One bounded/reaped DNS child; no shell, inherited credentials or retries."""
    code = "import socket,sys,json; a=sorted({r[4][0] for r in socket.getaddrinfo(sys.argv[1],443,type=socket.SOCK_STREAM)}); assert 0<len(a)<=64; print(json.dumps(a))"
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", code, host],
            capture_output=True,
            text=True,
            timeout=min(timeout, 3),
            env={"PATH": os.defpath},
            check=True,
        )
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, ValueError):
        raise PublicNetworkError("Public DNS resolution unavailable") from None
