"""Check repository-only audit tooling without adding script imports to installed backend tests."""

import json
import sys
import base64
import hashlib
import io
import tarfile

import pytest

from scripts.audit_dependencies import run_auditor
from scripts import audit_dependencies as audit


@pytest.mark.parametrize(
    ("report", "exit_code", "name", "expected"),
    [
        ({"dependencies": []}, 1, "python", "error"),
        ({"dependencies": [{"name": "unlisted", "skip_reason": "Not in registry"}]},
         0, "python", "incomplete"),
        ({"dependencies": [{"name": "affected", "vulns": [{"id": "CVE-example"}]}]},
         1, "python", "vulnerable"),
        ({"error": {"message": "Registry unavailable"}}, 1, "frontend", "error"),
    ],
)
def test_external_auditor_failures_remain_visible(tmp_path, report, exit_code, name, expected):
    """An actual failed/skipped auditor process must retain its evidence and block a clean result."""
    command = [sys.executable, "-c", "import sys; print(sys.argv[1]); sys.exit(int(sys.argv[2]))",
               json.dumps(report), str(exit_code)]
    receipt = run_auditor(command, tmp_path, name, cwd=tmp_path)
    assert receipt["status"] == expected
    assert receipt["exit_code"] == exit_code
    assert json.loads((tmp_path / f"{name}.stdout").read_text()) == report


def test_missing_auditor_is_an_error(tmp_path):
    """A missing local tool cannot silently produce a clean dependency audit."""
    receipt = run_auditor([str(tmp_path / "missing-auditor")], tmp_path, "python", cwd=tmp_path)
    assert receipt == {"status": "error", "error": "FileNotFoundError"}


def npm_archive(*, version="1.0.0", linked=False, archive_root="package", declared=True, license_text=None):
    """Build a real registry-shaped archive without installing or executing its contents."""
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        manifest = {"name": "example", "version": version}
        if declared:
            manifest["license"] = "MIT"
        content = json.dumps(manifest).encode()
        member = tarfile.TarInfo(f"{archive_root}/package.json")
        member.size = len(content)
        if linked:
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc/passwd"
            member.size = 0
        archive.addfile(member, None if linked else io.BytesIO(content))
        if license_text is not None:
            member = tarfile.TarInfo(f"{archive_root}/license")
            member.size = len(license_text.encode())
            archive.addfile(member, io.BytesIO(license_text.encode()))
    return output.getvalue()


@pytest.mark.parametrize("archive_root", ["package", "example"])
def test_missing_lock_license_is_read_from_integrity_verified_archive(monkeypatch, archive_root):
    """The version locked by npm supplies its declaration even when the lock omits that field."""
    content = npm_archive(archive_root=archive_root)
    monkeypatch.setattr(audit, "fetch_license_bytes", lambda url: content)
    pin = {"version": "1.0.0", "resolved": "https://registry.npmjs.org/example/-/example-1.0.0.tgz",
           "integrity": "sha512-" + base64.b64encode(hashlib.sha512(content).digest()).decode()}
    result = audit.npm_license(("node_modules/example", pin))
    assert result["status"] == "declared_artifact"
    assert result["declaration"] == "MIT"
    assert result["artifact_sha256"] == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize("failure", ["integrity", "version", "symlink"])
def test_archive_identity_and_nonregular_metadata_do_not_pass_as_licenses(monkeypatch, failure):
    """Corrupt downloads, wrong package versions and metadata links remain explicit audit errors."""
    content = npm_archive(version="9.0.0" if failure == "version" else "1.0.0",
                          linked=failure == "symlink")
    monkeypatch.setattr(audit, "fetch_license_bytes", lambda url: content)
    digest = hashlib.sha512(b"different" if failure == "integrity" else content).digest()
    pin = {"version": "1.0.0", "resolved": "https://registry.npmjs.org/example/-/example-1.0.0.tgz",
           "integrity": "sha512-" + base64.b64encode(digest).decode()}
    result = audit.npm_license(("node_modules/example", pin))
    assert result["status"] == "unavailable"
    assert not result.get("declaration")


@pytest.mark.parametrize("review_matches", [True, False])
def test_python_source_license_review_is_bound_to_artifact_bytes(tmp_path, monkeypatch, review_matches):
    """A prior license decision applies only to its reviewed archive, never merely the package name/version."""
    output = io.BytesIO()
    license_text = "MIT License\nExample copyright and complete fixture terms.\n"
    member_name = "example-1.0.0/LICENSE"
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        member = tarfile.TarInfo(member_name)
        member.size = len(license_text.encode())
        archive.addfile(member, io.BytesIO(license_text.encode()))
    content = output.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    reviews = tmp_path / "docs/modernization/license-artifact-reviews.json"
    reviews.parent.mkdir(parents=True)
    reviews.write_text(json.dumps([{"name": "example", "version": "1.0.0",
        "artifact_sha256": digest if review_matches else "0" * 64, "member": member_name,
        "member_sha256": hashlib.sha256(license_text.encode()).hexdigest(), "expression": "MIT"}]))
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "fetch_license_bytes", lambda url: content)
    row = {"name": "example", "version": "1.0.0", "status": "missing"}
    audit.python_artifact_license(row, [{"packagetype": "sdist", "url": "https://files.pythonhosted.org/example.tgz",
                                         "digests": {"sha256": digest}}])
    assert row["status"] == ("reviewed_artifact" if review_matches else "needs_review")
    assert bool(row.get("expression")) == review_matches
    assert row["artifact"]["license_files"][0]["text"] == license_text


@pytest.mark.parametrize("review_matches", [True, False])
def test_npm_missing_declaration_uses_only_an_exact_reviewed_license_file(tmp_path, monkeypatch, review_matches):
    """A license file can supply reviewed evidence without a manifest field; a stale artifact review must not approve it."""
    license_text = "The MIT License (MIT)\nCopyright fixture; permission and notice conditions retained.\n"
    content = npm_archive(declared=False, license_text=license_text)
    digest = hashlib.sha256(content).hexdigest()
    reviews = tmp_path / "docs/modernization/license-artifact-reviews.json"
    reviews.parent.mkdir(parents=True)
    reviews.write_text(json.dumps([{"name": "example", "version": "1.0.0", "artifact_sha256": digest if review_matches else "0" * 64,
        "member": "package/license", "member_sha256": hashlib.sha256(license_text.encode()).hexdigest(), "expression": "MIT"}]))
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "fetch_license_bytes", lambda url: content)
    pin = {"version": "1.0.0", "resolved": "https://registry.npmjs.org/example/-/example-1.0.0.tgz",
        "integrity": "sha512-" + base64.b64encode(hashlib.sha512(content).digest()).decode()}
    row = audit.npm_license(("node_modules/example", pin))
    assert row["status"] == ("reviewed_artifact" if review_matches else "needs_review")
    assert bool(row.get("expression")) == review_matches
