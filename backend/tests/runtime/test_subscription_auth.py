"""Host-owned subscription credentials never become model/user event payloads."""

import base64
import json

import pytest


def jwt(value="first"):
    def encode(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    return (
        encode({"alg": "RS256"})
        + "."
        + encode({"sub": value, "email": "test@example.invalid"})
        + ".synthetic"
    )


def auth_file(tmp_path, **changes):
    path = tmp_path / "auth.json"
    document = {
        "auth_mode": "chatgpt",
        "OPENAI_API_KEY": None,
        "tokens": {
            "access_token": jwt(),
            "account_id": "account-A",
            "refresh_token": "NEVER-FORWARD-REFRESH",
        },
    }
    document.update(changes)
    path.write_text(json.dumps(document))
    path.chmod(0o600)
    return path


def test_managed_source_exports_only_redacted_subscription_access_credentials(tmp_path):
    from backend.runtime.subscription_auth import ManagedTokenFile

    credential = ManagedTokenFile(auth_file(tmp_path)).read()
    assert credential.account_id == "account-A"
    assert credential.access_token == jwt()
    assert jwt() not in repr(credential) and "account-A" not in repr(credential)
    assert "refresh_token" not in credential.rpc_params()
    assert set(credential.rpc_params()) == {
        "accessToken",
        "chatgptAccountId",
        "chatgptPlanType",
    }


@pytest.mark.parametrize(
    "condition", ["missing", "public", "symlink", "malformed", "api_key", "oversized"]
)
def test_unsafe_or_non_subscription_sources_fail_without_creating_state(
    tmp_path, condition
):
    from backend.runtime.codex_session import SubscriptionRequired
    from backend.runtime.subscription_auth import ManagedTokenFile

    path = auth_file(tmp_path)
    if condition == "missing":
        path.unlink()
    elif condition == "public":
        path.chmod(0o644)
    elif condition == "symlink":
        path.rename(tmp_path / "original.json")
        path.symlink_to(tmp_path / "original.json")
    elif condition == "malformed":
        path.write_text("SECRET-MALFORMED-TOKEN")
    elif condition == "api_key":
        path = auth_file(tmp_path, auth_mode="apikey", OPENAI_API_KEY="SECRET-API-KEY")
    else:
        path.write_text("x" * 1048577)
    with pytest.raises(SubscriptionRequired) as error:
        ManagedTokenFile(path).read()
    assert "SECRET" not in str(error.value)
    if condition == "missing":
        assert not path.exists()
