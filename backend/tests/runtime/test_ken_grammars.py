"""Verify trusted offline grammar preparation and the real Ken worker cache boundary."""

import json
import hashlib
import os
import subprocess

import pytest

from backend.runtime.ken_grammars import cache_directory, prepare_grammars, verify_grammars
from backend.runtime.ken_worker import KenInstallation, worker_process


def test_worker_reads_the_trusted_grammar_cache_without_making_it_writable(
    ken_installation, tmp_path
):
    """The isolated worker must read provisioned grammars through its cache and preserve their bytes."""
    cache = ken_installation.parent.parent / "share/researcher-ken-cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "marker").write_text("TRUSTED_PUBLIC_GRAMMAR")
    ken_installation.write_text(
        "#!" + str(ken_installation.parent / "python") + "\n"
        "import os,json\nfrom pathlib import Path\n"
        "cache=Path(os.environ['XDG_CACHE_HOME'])\n"
        "result={'marker':(cache/'marker').read_text()}\n"
        "try:(cache/'marker').write_text('CHANGED')\n"
        "except OSError:result['write']='denied'\n"
        "print(json.dumps(result))\n"
    )
    workspace = tmp_path / "source"
    workspace.mkdir()
    with worker_process(KenInstallation.inspect(ken_installation), workspace=workspace) as launch:
        result = subprocess.run(
            launch.command, pass_fds=launch.pass_fds, env=launch.env,
            capture_output=True, text=True, timeout=10, check=False,
        )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"marker": "TRUSTED_PUBLIC_GRAMMAR", "write": "denied"}
    assert (cache / "marker").read_text() == "TRUSTED_PUBLIC_GRAMMAR"


@pytest.mark.parametrize("fault", ["missing", "changed", "symlink", "manifest"])
def test_incomplete_or_changed_grammars_refuse_admission_before_source_state(
    ken_installation, tmp_path, fault
):
    """A trusted installation receipt cannot hide missing, altered or redirected parser bytes before a worker starts."""
    installation = KenInstallation.inspect(ken_installation)
    cache = cache_directory(installation.tool_root)
    resource = cache / "tree-sitter-language-pack/v1.22.1/libs/libtree_sitter_python.so"
    if fault == "missing":
        resource.unlink()
    elif fault == "changed":
        content = resource.read_bytes()
        resource.write_bytes(b"X" * len(content))
    elif fault == "symlink":
        outside = tmp_path / "untrusted.so"
        resource.rename(outside)
        resource.symlink_to(outside)
    else:
        data = json.loads((cache / "manifest.json").read_text())
        data["version"] = "unexpected"
        (cache / "manifest.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        KenInstallation.inspect(ken_installation)
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError), worker_process(installation, workspace=source):
        pass
    assert not (source / ".ken").exists()


def test_preparation_preserves_an_invalid_existing_cache(ken_installation, tmp_path):
    """Explicit preparation must not overwrite unknown resources or silently repair a changed installation."""
    tool = ken_installation.parent.parent
    manifest = cache_directory(tool) / "manifest.json"
    manifest.write_text("retained invalid receipt")
    with pytest.raises(ValueError):
        prepare_grammars(tool, tmp_path / "not-read.tar.zst")
    assert manifest.read_text() == "retained invalid receipt"


def test_an_unpinned_archive_cannot_create_a_grammar_cache(tmp_path):
    """Preparation verifies the archive before creating any destination resource directory."""
    tool = tmp_path / "tool"
    tool.mkdir()
    archive = tmp_path / "untrusted.tar.zst"
    archive.write_bytes(b"not the pinned archive")
    with pytest.raises(ValueError, match="pinned"):
        prepare_grammars(tool, archive)
    assert not cache_directory(tool).parent.exists()


def test_grammar_checks_never_need_a_network_or_loader(ken_installation, monkeypatch):
    """Preflight reads declared bytes only; it neither runs Ken nor triggers a lazy parser download."""
    def unavailable(*args, **kwargs):
        """Reject any subprocess attempt from a local grammar-integrity check."""
        raise AssertionError("Preflight must not execute a loader")

    monkeypatch.setattr(subprocess, "Popen", unavailable)
    result = verify_grammars(ken_installation.parent.parent)
    assert result["files"] == 1


def test_an_inspected_installation_cannot_silently_use_a_replaced_grammar_manifest(ken_installation, tmp_path):
    """A newly consistent cache has a different identity and cannot reuse the original admission snapshot."""
    installation = KenInstallation.inspect(ken_installation)
    cache = cache_directory(installation.tool_root)
    resource = cache / "tree-sitter-language-pack/v1.22.1/libs/libtree_sitter_python.so"
    replacement = b"DIFFERENT_TRUSTED_INSTALLATION_BYTES"
    resource.write_bytes(replacement)
    manifest = json.loads((cache / "manifest.json").read_text())
    manifest["files"][resource.name] = {"bytes": len(replacement), "sha256": hashlib.sha256(replacement).hexdigest()}
    (cache / "manifest.json").write_text(json.dumps(manifest))
    assert verify_grammars(installation.tool_root)["fingerprint"] != installation.grammar_fingerprint
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="changed after"), worker_process(installation, workspace=source):
        pass
    assert not (source / ".ken").exists()
