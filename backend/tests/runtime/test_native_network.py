"""Explicit public DNS/CA material is pinned; no managed credential mount."""

import os
import ssl
from pathlib import Path

import pytest


def public_inputs(tmp_path):
    resolver = tmp_path / "resolv.conf"
    resolver.write_text("nameserver 127.0.0.1\noptions timeout:1 attempts:1\n")
    ca = tmp_path / "ca.pem"
    ca.write_bytes(Path(ssl.get_default_verify_paths().cafile).read_bytes())
    resolver.chmod(0o600)
    ca.chmod(0o600)
    return resolver, ca


def test_public_network_inputs_are_inspected_and_bound_to_content(tmp_path):
    from backend.runtime.native_network import NativeNetwork

    resolver, ca = public_inputs(tmp_path)
    network = NativeNetwork.inspect(resolver=resolver, ca_bundle=ca)
    assert network.resolver.path == str(resolver)
    assert network.ca_bundle.path == str(ca)
    assert len(network.ca_bundle.sha256) == 64
    with network.opened() as fds:
        assert (
            os.read(fds["resolver"], 65536)
            == b"nameserver 127.0.0.1\noptions timeout:1 attempts:1\n"
        )
        with pytest.raises(PermissionError):
            os.write(fds["resolver"], b"changed")
    ca.write_text("changed")
    with pytest.raises(ValueError, match="network"), network.opened():
        pytest.fail("Changed trust roots were admitted")


@pytest.mark.parametrize(
    "condition",
    [
        "missing",
        "public_writer",
        "fifo",
        "bad_dns",
        "bad_ca",
        "private_key",
        "oversized",
    ],
)
def test_invalid_network_inputs_fail_before_a_payload_can_start(tmp_path, condition):
    from backend.runtime.native_network import NativeNetwork

    resolver, ca = public_inputs(tmp_path)
    if condition == "missing":
        resolver.unlink()
    elif condition == "public_writer":
        resolver.chmod(0o666)
    elif condition == "fifo":
        resolver.unlink()
        os.mkfifo(resolver, 0o600)
    elif condition == "bad_dns":
        resolver.write_text("nameserver attacker.invalid\n")
    elif condition == "bad_ca":
        ca.write_text("not a certificate")
    elif condition == "private_key":
        with ca.open("a") as f:
            f.write(
                "\n-----BEGIN PRIVATE KEY-----\nSECRET\n-----END PRIVATE KEY-----\n"
            )
    else:
        resolver.write_bytes(b"x" * 65537)
    with pytest.raises(ValueError) as error:
        NativeNetwork.inspect(resolver=resolver, ca_bundle=ca)
    assert "SECRET" not in str(error.value)
