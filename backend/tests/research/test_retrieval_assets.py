"""Explicit setup and pinned local assets must not trigger downloads during serving."""

import pytest


def test_bootstrap_help_exposes_explicit_model_preparation_without_loading_models(
    capsys,
):
    """Make local retrieval setup discoverable while preserving inference-free help."""
    from backend.cli.bootstrap import main

    with pytest.raises(SystemExit) as result:
        main(["--help"])
    assert result.value.code == 0
    assert "prepare-retrieval" in capsys.readouterr().out


def test_preparation_refuses_an_existing_unverified_directory_without_modifying_it(
    tmp_path, capsys
):
    """Model setup must not adopt, repair or overwrite an arbitrary existing location."""
    from backend.cli.bootstrap import main

    target = tmp_path / "existing"
    target.mkdir()
    secret = target / "keep.txt"
    secret.write_text("Preserve me")
    assert (
        main(
            [
                "prepare-retrieval",
                "--directory",
                str(target),
                "--cache-dir",
                str(tmp_path / "cache"),
                "--offline",
            ]
        )
        == 1
    )
    assert secret.read_text() == "Preserve me"
    assert sorted(p.name for p in target.iterdir()) == ["keep.txt"]


def test_runtime_refuses_a_symlink_even_when_target_has_expected_bytes(
    monkeypatch, tmp_path
):
    """Runtime asset descriptors must not follow mutable cache/user symlinks."""
    import hashlib

    import backend.research.retrieval_assets as module

    target = tmp_path / "outside"
    target.write_bytes(b"abc")
    root = tmp_path / "model"
    root.mkdir()
    (root / "model.onnx").symlink_to(target)
    monkeypatch.setattr(
        module,
        "ARTIFACTS",
        {"model.onnx": ("model.onnx", 3, hashlib.sha256(b"abc").hexdigest())},
    )
    with pytest.raises(module.RetrievalUnavailable), module.pinned_assets(root):
        pass
    assert target.read_bytes() == b"abc"


def test_asset_growing_during_verification_cannot_exceed_declared_read_budget(
    monkeypatch, tmp_path
):
    """An update racing verification must fail boundedly instead of hashing an ever-growing file."""
    import hashlib

    import backend.research.retrieval_assets as module

    file = tmp_path / "model.onnx"
    file.write_bytes(b"abc")
    monkeypatch.setattr(
        module,
        "ARTIFACTS",
        {"model.onnx": ("model.onnx", 3, hashlib.sha256(b"abc").hexdigest())},
    )
    original = module.os.read
    calls = []

    def growing(fd, count):
        """Append on every later read, simulating a deployment changing a pinned inode."""
        calls.append(1)
        assert len(calls) <= 3, "Verification read beyond the declared asset budget"
        if len(calls) > 1:
            with file.open("ab") as output:
                output.write(b"def")
        return original(fd, count)

    monkeypatch.setattr(module.os, "read", growing)
    with pytest.raises(module.RetrievalUnavailable), module.pinned_assets(tmp_path):
        pass
