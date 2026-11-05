"""Real pipe EOF must follow the delivered post-gate writer, not a hidden broker duplicate."""

import os
from types import SimpleNamespace


def test_post_gate_transport_can_finish_stdin_without_retiring_the_process():
    """A child such as git update-ref must see EOF after its caller finishes transaction input."""
    from backend.runtime.peer_broker import PeerTransport

    read, write = os.pipe()
    os.set_blocking(read, False)
    with (
        os.fdopen(write, "wb", buffering=0) as stdin,
        open(os.devnull, "rb") as stdout,
        open(os.devnull, "rb") as stderr,
    ):
        owner = SimpleNamespace(
            stdin=stdin, stdout=stdout, stderr=stderr, wait=lambda **_: 0
        )
        transport = PeerTransport(owner)
        try:
            transport.stdin.write(b"commit\n")
            transport.stdin.close()
            assert os.read(read, 100) == b"commit\n"
            assert os.read(read, 100) == b""
        finally:
            transport.close_handles()
            os.close(read)
