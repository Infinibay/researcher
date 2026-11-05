"""Remote host transport contracts; synthetic secrets and temporary inputs are not user credentials."""

import json

import pytest


def test_remote_transport_reads_private_credential_without_serializing_secret(tmp_path):
    """An operator credential stays outside source and public launch identity; unsafe file permissions are rejected."""
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.remote_transport import RemoteTransportConfig

    path = tmp_path / "token"
    path.write_text("synthetic-forgejo-pat")
    path.chmod(0o600)
    network = NativeNetwork.inspect(
        resolver="/etc/resolv.conf", ca_bundle="/etc/ssl/certs/ca-certificates.crt"
    )
    config = RemoteTransportConfig(
        "https://forgejo.example/api/v1", "fixture-user", path, network
    )
    assert config.token() == "synthetic-forgejo-pat"
    assert "synthetic-forgejo-pat" not in json.dumps(config.public_manifest())
    path.chmod(0o644)
    with pytest.raises(ValueError):
        config.token()


async def test_http_write_hook_runs_at_write_boundary_and_read_hook_cannot_grant_another_write():
    """Actual HTTP transport callbacks guard each request, with one effect reservation only when a real POST is about to begin."""
    import httpx

    from backend.runtime.forgejo_publication import ForgejoPublicationClient

    events = []

    async def before_request():
        """Represent live original lease validation, not an inferred grant from a prior read."""
        events.append("authority")

    async def before_write(method, url, payload):
        """Reserve the exact write only after its read preflight and before transport release."""
        assert method == "POST" and payload == {"body": "original"}
        events.append("issued")

    def server(request):
        """Keep actual HTTPX method/body framing while recording the order seen by this controlled provider."""
        events.append(request.method)
        return httpx.Response(200, json={})

    async with ForgejoPublicationClient(
        "https://forgejo.example/api/v1",
        "synthetic-pat",
        transport=httpx.MockTransport(server),
        before_request=before_request,
        before_write=before_write,
    ) as client:
        await client._request("GET", "https://forgejo.example/api/v1/repos/o/r")
        await client._request(
            "POST",
            "https://forgejo.example/api/v1/repos/o/r/pulls",
            payload={"body": "original"},
        )
    assert events == ["authority", "GET", "authority", "issued", "POST"]
