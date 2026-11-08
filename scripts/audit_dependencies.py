"""Audit committed dependency versions and inventory declared licenses without installing project packages.

Requires Python 3.12+, uv and npm. Advisory reports are evidence of known issues,
not proof of exploitability or absence of vulnerabilities. License metadata is
an inventory for review, never an automatic license-compatibility approval.
"""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tomllib
from urllib.request import urlopen
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
AUDITOR = "pip-audit==2.10.1"
MAX_LICENSE_DOWNLOAD = 16 * 1024 * 1024


def fetch_license_bytes(url):
    """Read bounded public registry evidence; never install packages or invoke their build hooks."""
    allowed = {"pypi.org", "files.pythonhosted.org", "registry.npmjs.org"}
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in allowed or parsed.username or parsed.port:
        raise ValueError("Unsupported license evidence URL")
    with urlopen(url, timeout=15) as response:
        if urlsplit(response.url).hostname not in allowed:
            raise ValueError("Unexpected license evidence redirect")
        content = response.read(MAX_LICENSE_DOWNLOAD + 1)
    if len(content) > MAX_LICENSE_DOWNLOAD:
        raise ValueError("License evidence exceeds download limit")
    return content


def license_archive_members(content):
    """Read shallow declarations and license files from a bounded tar, without extracting any path."""
    selected = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(content), mode="r|gz") as archive:
        for index, member in enumerate(archive):
            total += member.size
            if index >= 10000 or total > 64 * 1024 * 1024:
                raise ValueError("License archive exceeds inspection limits")
            name = Path(member.name).name
            wanted = member.name.count("/") <= 2 and (
                name == "package.json" or name.lower().startswith(("license", "licence", "copying", "notice")))
            if not wanted:
                continue
            if not member.isfile() or member.size > 1024 * 1024 or member.name in selected:
                raise ValueError("Invalid license evidence member")
            selected[member.name] = archive.extractfile(member).read().decode("utf-8")
    return selected



def artifact_review(name, version, digest, members):
    """Reuse a manual license decision only for the exact package archive and license-file bytes reviewed."""
    path = ROOT / "docs/modernization/license-artifact-reviews.json"
    reviews = json.loads(path.read_text()) if path.exists() else []
    for review in reviews:
        if (review["name"], review["version"], review["artifact_sha256"]) != (name, version, digest):
            continue
        text = members.get(review["member"])
        if text is not None and hashlib.sha256(text.encode()).hexdigest() == review["member_sha256"]:
            return review
    return None


def npm_license(item):
    """Fill a missing npm lock declaration from the exact integrity-verified package archive."""
    path, pin = item
    row = {"path": path, "version": pin["version"], "declaration": pin.get("license"),
           "status": "declared" if pin.get("license") else "missing"}
    if row["declaration"]:
        return row
    try:
        content = fetch_license_bytes(pin["resolved"])
        algorithm, encoded = pin["integrity"].split("-", 1)
        if algorithm not in {"sha512", "sha256", "sha1"}:
            raise ValueError("Unsupported package integrity")
        if hashlib.new(algorithm, content).digest() != base64.b64decode(encoded, validate=True):
            raise ValueError("Package integrity mismatch")
        members = license_archive_members(content)
        package_files = [text for name, text in members.items()
                         if name.count("/") == 1 and Path(name).name == "package.json"]
        if len(package_files) != 1:
            raise ValueError("Expected exactly one root package manifest")
        package = json.loads(package_files[0])
        if package["version"] != pin["version"] or package["name"] != path.rsplit("node_modules/", 1)[1]:
            raise ValueError("Package identity mismatch")
        declaration = package.get("license")
        if isinstance(declaration, dict):
            declaration = declaration.get("type")
        if not isinstance(declaration, str) or not declaration.strip():
            declaration = None
        digest = hashlib.sha256(content).hexdigest()
        row.update(declaration=declaration, source=pin["resolved"],
                   artifact_sha256=digest,
                   status="declared_artifact" if declaration else "missing")
        if declaration is None:
            files = {name: text for name, text in members.items() if Path(name).name != "package.json"}
            review = artifact_review(package["name"], package["version"], digest, files)
            if review is not None:
                row.update(expression=review["expression"], status="reviewed_artifact", review=review)
            elif files:
                row["status"] = "needs_review"
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as exc:
        row.update(status="unavailable", error=f"{type(exc).__name__}: {exc}")
    return row


def python_artifact_license(row, releases):
    """Attach source license text and accept only a human-readable review bound to the exact archive hash."""
    artifact = next((a for a in releases if a["packagetype"] == "sdist"), None)
    if artifact is None:
        return
    content = fetch_license_bytes(artifact["url"])
    digest = hashlib.sha256(content).hexdigest()
    if digest != artifact["digests"]["sha256"]:
        raise ValueError("Python artifact digest mismatch")
    members = license_archive_members(content)
    files = [{"path": path, "sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text}
             for path, text in sorted(members.items())]
    row["artifact"] = {"url": artifact["url"], "sha256": digest, "license_files": files}
    review = artifact_review(row["name"], row["version"], digest, members)
    if review is not None:
        row.update(expression=review["expression"], status="reviewed_artifact", review=review)
        return
    row["status"] = "needs_review" if files else "missing"


def write_json(path, value):
    """Write a stable inspectable report, including failed and incomplete observations."""
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def locked_scopes():
    """Read every registry package in product/script locks and the isolated Ken requirements."""
    scopes = {}
    for path in [ROOT / "uv.lock", *sorted((ROOT / "scripts").glob("*.py.lock"))]:
        packages = tomllib.loads(path.read_text())["package"]
        pins = sorted({(p["name"], p["version"]) for p in packages if "registry" in p["source"]})
        scopes[str(path.relative_to(ROOT))] = pins
    ken = ROOT / "requirements-ken.txt"
    scopes[ken.name] = sorted(set(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", ken.read_text(), re.M)))
    if any(not pins for pins in scopes.values()):
        raise ValueError("A committed dependency scope contained no registry pins")
    return scopes


def run_auditor(command, output, name, *, cwd):
    """Retain both process status and raw output; a timeout or invalid report never means clean."""
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "error", "error": type(exc).__name__}
    (output / f"{name}.stdout").write_text(result.stdout)
    (output / f"{name}.stderr").write_text(result.stderr)
    try:
        report = json.loads(result.stdout)
        if name == "frontend":
            count = report["metadata"]["vulnerabilities"]["total"]
            skipped = []
            ids = sorted({str(via["source"]) for row in report["vulnerabilities"].values()
                          for via in row["via"] if isinstance(via, dict)})
        else:
            dependencies = report["dependencies"]
            count = sum(len(row.get("vulns", [])) for row in dependencies)
            ids = sorted({v["id"] for row in dependencies for v in row.get("vulns", [])})
            skipped = [{"name": row["name"], "reason": row["skip_reason"]}
                       for row in dependencies if row.get("skip_reason")]
        expected_exit = 1 if count else 0
        status = "incomplete" if skipped else "vulnerable" if count else "clean"
        if result.returncode != expected_exit:
            status = "error"
        return {"status": status, "exit_code": result.returncode,
                "advisory_entries": count, "advisory_ids": ids, "skipped": skipped}
    except (ValueError, KeyError, TypeError):
        return {"status": "error", "exit_code": result.returncode, "error": "invalid_report"}


def declared_license(pin):
    """Read version-specific PyPI declarations, falling back to reviewed source bytes without execution."""
    name, version = pin
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    row = {"name": name, "version": version, "source": url}
    try:
        metadata = json.loads(fetch_license_bytes(url))
        info = metadata["info"]
        row.update(expression=info.get("license_expression"), declaration=info.get("license"),
                   classifiers=[c for c in info.get("classifiers", []) if c.startswith("License ::")])
        row["status"] = "declared" if any(row[key] for key in ("expression", "declaration", "classifiers")) else "missing"
        if row["status"] == "missing":
            python_artifact_license(row, metadata["urls"])
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as exc:
        row.update(status="unavailable", error=type(exc).__name__)
    return row


def license_inventory(scopes):
    """Inventory all locked versions, preserving failures and artifact review provenance."""
    pins = sorted({pin for rows in scopes.values() for pin in rows})
    with ThreadPoolExecutor(max_workers=6) as workers:
        python = list(workers.map(declared_license, pins))
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text())
    with ThreadPoolExecutor(max_workers=6) as workers:
        frontend = list(workers.map(npm_license, ((path, row) for path, row in lock["packages"].items() if path)))
    inputs = [*scopes, "frontend/package-lock.json", "docs/modernization/license-artifact-reviews.json"]
    return {"interpretation": "Declarations and explicitly reviewed artifacts; no automatic compatibility approval.",
            "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                             for path in inputs if (ROOT / path).is_file()},
            "python": python, "frontend": frontend,
            "unavailable": sum(row["status"] == "unavailable" for row in python + frontend),
            "needs_review": sum(row["status"] == "needs_review" for row in python + frontend),
            "missing": sum(row["status"] == "missing" for row in python + frontend)}


def main():
    """Run every scope even after known findings, write the summary, and fail for any incomplete audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New report directory")
    parser.add_argument("--licenses", action="store_true", help="Also inventory licenses with verified artifact fallbacks")
    parser.add_argument("--licenses-only", action="store_true", help="Inventory licenses without repeating vulnerability audits")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    scopes = locked_scopes()
    if args.licenses_only:
        licenses = license_inventory(scopes)
        write_json(output / "licenses.json", licenses)
        return 2 if any(licenses[key] for key in ("unavailable", "missing", "needs_review")) else 0
    summary = {"observed_at": datetime.now(timezone.utc).isoformat(), "auditor": AUDITOR,
               "scope": "All registry versions in committed locks, including optional/platform variants",
               "scopes": {}}
    for source, pins in scopes.items():
        name = Path(source).name.replace(".", "-")
        requirements = output / f"{name}.txt"
        requirements.write_text("".join(f"{package}=={version}\n" for package, version in pins))
        receipt = run_auditor(["uvx", "--from", AUDITOR, "pip-audit", "--no-deps", "--disable-pip",
                               "--format", "json", "-r", str(requirements)], output, name, cwd=ROOT)
        receipt.update(packages=len(pins), input_sha256=hashlib.sha256((ROOT / source).read_bytes()).hexdigest())
        summary["scopes"][source] = receipt
        print(f"{source}: {receipt['status']}", flush=True)
    summary["scopes"]["frontend/package-lock.json"] = run_auditor(
        ["npm", "audit", "--json"], output, "frontend", cwd=ROOT / "frontend")
    summary["scopes"]["frontend/package-lock.json"]["input_sha256"] = hashlib.sha256(
        (ROOT / "frontend/package-lock.json").read_bytes()).hexdigest()
    if args.licenses:
        licenses = license_inventory(scopes)
        write_json(output / "licenses.json", licenses)
        summary["licenses"] = {"unavailable": licenses["unavailable"], "missing": licenses["missing"],
                               "needs_review": licenses["needs_review"],
                               "compatibility_review": "pending"}
    incomplete = any(row["status"] in {"error", "incomplete"} for row in summary["scopes"].values())
    incomplete |= bool(summary.get("licenses", {}).get("unavailable"))
    incomplete |= any(summary.get("licenses", {}).get(key) for key in ("missing", "needs_review"))
    vulnerable = any(row.get("advisory_entries", 0) for row in summary["scopes"].values())
    summary["exit_code"] = 2 if incomplete else 1 if vulnerable else 0
    write_json(output / "summary.json", summary)
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
