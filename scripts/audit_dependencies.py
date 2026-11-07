"""Audit committed dependency versions and inventory declared licenses without installing project packages.

Requires Python 3.12+, uv and npm. Advisory reports are evidence of known issues,
not proof of exploitability or absence of vulnerabilities. License metadata is
an inventory for review, never an automatic license-compatibility approval.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
AUDITOR = "pip-audit==2.10.1"


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
    """Fetch version-specific PyPI declarations without downloading or executing the distribution."""
    name, version = pin
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    row = {"name": name, "version": version, "source": url}
    try:
        with urlopen(url, timeout=15) as response:
            info = json.load(response)["info"]
        row.update(expression=info.get("license_expression"), declaration=info.get("license"),
                   classifiers=[c for c in info.get("classifiers", []) if c.startswith("License ::")])
        row["status"] = "declared" if any(row[key] for key in ("expression", "declaration", "classifiers")) else "missing"
    except (OSError, ValueError, KeyError) as exc:
        row.update(status="unavailable", error=type(exc).__name__)
    return row


def license_inventory(scopes):
    """Keep missing declarations visible across all Python scopes and the complete npm lock."""
    pins = sorted({pin for rows in scopes.values() for pin in rows})
    with ThreadPoolExecutor(max_workers=6) as workers:
        python = list(workers.map(declared_license, pins))
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text())
    frontend = [{"path": path, "version": row["version"], "declaration": row.get("license"),
                 "status": "declared" if row.get("license") else "missing"}
                for path, row in lock["packages"].items() if path]
    return {"interpretation": "Registry/lock declarations only; compatibility review is pending.",
            "python": python, "frontend": frontend,
            "unavailable": sum(row["status"] == "unavailable" for row in python),
            "missing": sum(row["status"] == "missing" for row in python + frontend)}


def main():
    """Run every scope even after known findings, write the summary, and fail for any incomplete audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New report directory")
    parser.add_argument("--licenses", action="store_true", help="Also fetch declared PyPI license metadata")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    scopes = locked_scopes()
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
                               "compatibility_review": "pending"}
    incomplete = any(row["status"] in {"error", "incomplete"} for row in summary["scopes"].values())
    incomplete |= bool(summary.get("licenses", {}).get("unavailable"))
    vulnerable = any(row.get("advisory_entries", 0) for row in summary["scopes"].values())
    summary["exit_code"] = 2 if incomplete else 1 if vulnerable else 0
    write_json(output / "summary.json", summary)
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
