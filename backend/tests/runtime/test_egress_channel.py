"""FD delivery crosses a real private socket pair, never a host TCP listener."""

import array
import socket

import pytest

from backend.tests.runtime.test_egress_proxy import gate, response

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


def send_fd(sender, descriptors, payload=b"F"):
    sender.sendmsg(
        [payload],
        [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", descriptors))],
    )


def test_received_stream_uses_host_gate_and_helper_exit_closes_tunnel():
    from backend.runtime.egress_channel import EgressChannel

    proxy, calls, remotes = gate()
    channel = EgressChannel(proxy)
    sender = socket.socket(fileno=channel.duplicate_child())
    channel.close_child_end()
    client, accepted = socket.socketpair()
    try:
        with client, accepted:
            client.settimeout(1)
            send_fd(sender, [accepted.fileno()])
            accepted.close()
            client.sendall(
                b"CONNECT allowed.example:443 HTTP/1.1\r\nHost: allowed.example:443\r\n\r\n"
            )
            assert response(client).startswith(b"HTTP/1.1 200")
            client.sendall(b"test")
            remotes[0].settimeout(1)
            assert remotes[0].recv(4) == b"test"
            sender.close()
            assert client.recv(1) == b""
        assert calls == [("93.184.216.34", 443)]
    finally:
        sender.close()
        channel.close()
        for raw in remotes:
            raw.close()


@pytest.mark.parametrize("condition", ["extra_fd", "wrong_marker", "not_socket"])
def test_invalid_fd_delivery_retires_channel_without_dial(tmp_path, condition):
    from backend.runtime.egress_channel import EgressChannel

    proxy, calls, _remotes = gate()
    channel = EgressChannel(proxy)
    sender = socket.socket(fileno=channel.duplicate_child())
    channel.close_child_end()
    client, accepted = socket.socketpair()
    try:
        with client, accepted, sender:
            sender.settimeout(1)
            client.settimeout(1)
            if condition == "not_socket":
                with (tmp_path / "ordinary").open("w") as f:
                    send_fd(sender, [f.fileno()])
            else:
                send_fd(
                    sender,
                    [accepted.fileno()] * (2 if condition == "extra_fd" else 1),
                    b"X" if condition == "wrong_marker" else b"F",
                )
            accepted.close()
            assert sender.recv(1) == b""
            assert client.recv(1) == b""
            assert not calls
    finally:
        channel.close()
