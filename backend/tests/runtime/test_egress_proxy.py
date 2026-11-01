"""Connected byte streams exercise a bounded host CONNECT gate without Internet."""

import socket
import threading

import pytest


def gate(*, addresses=("93.184.216.34",), **limits):
    from backend.runtime.egress_proxy import EgressPolicy, TunnelProxy

    calls, readers = [], []

    def resolve(host, timeout):
        return list(addresses)

    def dial(address, port, timeout, admit):
        calls.append((address, port))
        client, remote = socket.socketpair()
        readers.append(remote)
        admit(client)
        return client

    proxy = TunnelProxy(
        EgressPolicy(("allowed.example",), **limits), resolver=resolve, dial=dial
    )
    return proxy, calls, readers


def incoming(
    proxy,
    request=b"CONNECT allowed.example:443 HTTP/1.1\r\nHost: allowed.example:443\r\n\r\n",
):
    client, host = socket.socketpair()
    client.settimeout(2)
    future = proxy.submit(host)
    client.sendall(request)
    return client, future


def response(client):
    result = b""
    while b"\r\n\r\n" not in result:
        block = client.recv(4096)
        if not block:
            break
        result += block
    return result


def test_connect_preserves_bytes_half_close_and_pins_public_numeric_address():
    proxy, calls, remotes = gate()
    try:
        client, future = incoming(proxy)
        with client:
            assert response(client) == b"HTTP/1.1 200 Connection Established\r\n\r\n"
            client.sendall(b"ping")
            client.shutdown(socket.SHUT_WR)
            with remotes[0] as remote:
                remote.settimeout(1)
                assert remote.recv(4) == b"ping"
                assert remote.recv(1) == b""
                remote.sendall(b"PONG")
                remote.shutdown(socket.SHUT_WR)
                assert client.recv(4) == b"PONG"
                assert client.recv(1) == b""
        receipt = future.result(timeout=1)
        assert (receipt.outcome, receipt.uploaded, receipt.downloaded) == (
            "completed",
            4,
            4,
        )
        assert calls == [("93.184.216.34", 443)]
    finally:
        proxy.close()


@pytest.mark.parametrize(
    "wire",
    [
        b"GET https://allowed.example/ HTTP/1.1\r\nHost: allowed.example\r\n\r\n",
        b"CONNECT denied.example:443 HTTP/1.1\r\nHost: denied.example:443\r\n\r\n",
        b"CONNECT allowed.example:80 HTTP/1.1\r\nHost: allowed.example:80\r\n\r\n",
        b"CONNECT allowed.example:443 HTTP/1.1\r\nHost: denied.example\r\n\r\n",
        b"CONNECT allowed.example:443 HTTP/1.1\r\nHost: allowed.example\r\nHost: allowed.example\r\n\r\n",
        b"CONNECT allowed.example:443 HTTP/1.1\r\nHost: allowed.example\r\nContent-Length: 0\r\n\r\n",
        b"CONNECT user:SECRET@allowed.example:443 HTTP/1.1\r\n\r\n",
        b"CONNECT 127.0.0.1:443 HTTP/1.1\r\n\r\n",
        b"CONNECT allowed.example.:443 HTTP/1.1\r\n\r\n",
    ],
)
def test_invalid_or_disallowed_connect_does_not_dial_or_echo_input(wire):
    proxy, calls, _remotes = gate()
    try:
        client, future = incoming(proxy, wire)
        with client:
            reply = response(client)
        receipt = future.result(timeout=1)
        assert reply.startswith(b"HTTP/1.1 403")
        assert receipt.outcome == "denied" and calls == []
        assert b"SECRET" not in reply and "SECRET" not in repr(receipt)
    finally:
        proxy.close()


@pytest.mark.parametrize(
    "private",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "2002:5db8:d822::1",
        "64:ff9b::7f00:1",
        "fe80::1%lo",
        "2606:4700:4700::1111%lo",
    ],
)
def test_any_non_public_dns_answer_rejects_the_entire_destination(private):
    proxy, calls, _remotes = gate(addresses=("93.184.216.34", private))
    try:
        client, future = incoming(proxy)
        with client:
            assert response(client).startswith(b"HTTP/1.1 403")
        assert future.result(timeout=1).outcome == "denied" and not calls
    finally:
        proxy.close()


def test_stop_closes_active_tunnels_and_refuses_new_streams():
    proxy, _calls, remotes = gate()
    try:
        client, future = incoming(proxy)
        with client:
            assert response(client).startswith(b"HTTP/1.1 200")
            proxy.withdraw()
            assert client.recv(1) == b""
            assert future.result(timeout=1).outcome == "withdrawn"
        with remotes[0] as remote:
            remote.settimeout(1)
            assert remote.recv(1) == b""
        later, host = socket.socketpair()
        with later, pytest.raises(RuntimeError):
            proxy.submit(host)
    finally:
        proxy.close()


def test_byte_limit_cannot_forward_an_extra_byte():
    proxy, _calls, remotes = gate(max_bytes=4)
    try:
        client, future = incoming(proxy)
        with client:
            assert response(client).startswith(b"HTTP/1.1 200")
            client.sendall(b"12345")
            receipt = future.result(timeout=1)
        with remotes[0] as remote:
            assert remote.recv(10) == b"1234"
            assert remote.recv(1) == b""
        assert receipt.outcome == "byte_limit" and receipt.uploaded == 4
    finally:
        proxy.close()


def test_idle_and_total_connection_budgets_are_enforced():
    proxy, _calls, remotes = gate(idle_seconds=0.05, max_connections=1)
    try:
        client, future = incoming(proxy)
        with client:
            assert response(client).startswith(b"HTTP/1.1 200")
            assert future.result(timeout=1).outcome == "deadline"
        remotes[0].close()
        later, host = socket.socketpair()
        with later, pytest.raises(RuntimeError):
            proxy.submit(host)
    finally:
        proxy.close()


def test_withdrawal_during_resolution_cannot_start_a_late_connection():
    from backend.runtime.egress_proxy import EgressPolicy, TunnelProxy

    entered, release = threading.Event(), threading.Event()
    calls = []

    def resolve(host, timeout):
        entered.set()
        assert release.wait(1)
        return ["93.184.216.34"]

    def forbidden_dial(*args):
        calls.append(args)
        pytest.fail("Connection started after withdrawal")

    proxy = TunnelProxy(
        EgressPolicy(("allowed.example",)), resolver=resolve, dial=forbidden_dial
    )
    try:
        client, future = incoming(proxy)
        with client:
            assert entered.wait(1)
            proxy.withdraw()
            release.set()
            assert future.result(timeout=1).outcome == "withdrawn"
            assert not calls
    finally:
        release.set()
        proxy.close()


def test_total_wall_deadline_also_bounds_an_incomplete_connect_header():
    proxy, calls, _remotes = gate(wall_seconds=0.05, header_seconds=1)
    try:
        client, future = incoming(proxy, b"CONNECT allowed.example:443 HTTP/1.1\r\n")
        with client:
            assert future.result(timeout=0.3).outcome == "deadline"
            assert not calls
    finally:
        proxy.close()


def test_shared_byte_budget_stops_other_connections_too():
    proxy, _calls, remotes = gate(max_bytes=100, max_total_bytes=4)
    try:
        a, first = incoming(proxy)
        b, second = incoming(proxy)
        with a, b:
            assert response(a).startswith(b"HTTP/1.1 200")
            assert response(b).startswith(b"HTTP/1.1 200")
            a.sendall(b"123")
            remotes[0].settimeout(1)
            assert remotes[0].recv(3) == b"123"
            b.sendall(b"45")
            for remote in remotes:
                remote.settimeout(1)
            assert remotes[1].recv(2) == b"4"
            assert first.result(timeout=1).outcome == "byte_limit"
            assert second.result(timeout=1).uploaded == 1
    finally:
        for remote in remotes:
            remote.close()
        proxy.close()


@pytest.mark.parametrize("addresses", [(), ("not-an-ip",), ("93.184.216.34",) * 65])
def test_invalid_or_unbounded_dns_results_never_dial(addresses):
    proxy, calls, _remotes = gate(addresses=addresses)
    try:
        client, future = incoming(proxy)
        with client:
            assert response(client).startswith(b"HTTP/1.1 403")
        assert future.result(timeout=1).outcome == "denied" and not calls
    finally:
        proxy.close()


def test_saturated_gate_does_not_retire_an_existing_tunnel():
    proxy, _calls, remotes = gate(max_tunnels=1)
    try:
        client, future = incoming(proxy)
        with client:
            assert response(client).startswith(b"HTTP/1.1 200")
            overflow, host = socket.socketpair()
            with overflow, pytest.raises(RuntimeError):
                proxy.submit(host)
            client.sendall(b"live")
            remotes[0].settimeout(1)
            assert remotes[0].recv(4) == b"live"
            proxy.withdraw()
            assert future.result(timeout=1).uploaded == 4
    finally:
        for remote in remotes:
            remote.close()
        proxy.close()


def test_late_dial_after_stop_closes_its_socket_without_forwarding():
    from backend.runtime.egress_proxy import EgressPolicy, TunnelProxy

    entered, release = threading.Event(), threading.Event()
    retained = []

    def dial(address, port, timeout, admit):
        raw, remote = socket.socketpair()
        retained.extend((raw, remote))
        entered.set()
        assert release.wait(1)
        admit(raw)
        return raw

    proxy = TunnelProxy(
        EgressPolicy(("allowed.example",)),
        resolver=lambda *_: ["93.184.216.34"],
        dial=dial,
    )
    try:
        client, future = incoming(proxy)
        with client:
            assert entered.wait(1)
            proxy.withdraw()
            release.set()
            assert future.result(timeout=1).outcome == "withdrawn"
            assert retained[0].fileno() == -1
            retained[1].settimeout(1)
            assert retained[1].recv(1) == b""
    finally:
        release.set()
        proxy.close()
        for raw in retained:
            raw.close()


def test_dependency_errors_do_not_expose_headers_or_secrets():
    from backend.runtime.egress_proxy import EgressPolicy, TunnelProxy

    def failed_resolver(*_):
        raise RuntimeError("SECRET-DNS-PROVIDER")

    proxy = TunnelProxy(EgressPolicy(("allowed.example",)), resolver=failed_resolver)
    try:
        client, future = incoming(proxy)
        with client:
            result = response(client)
        receipt = future.result(timeout=1)
        assert receipt.outcome == "io_error"
        assert b"SECRET" not in result and "SECRET" not in repr(receipt)
    finally:
        proxy.close()
