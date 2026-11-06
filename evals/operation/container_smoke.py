"""Exercise an installed service image with synthetic data and no model or account.

Run with the project's Python environment after building the image. This checks
owner HTTP, built web assets, attachment persistence and process restart, not
native agent admission or full deployment restoration. Podman storage is selected
by the caller; an optional JSON command prefix supports isolated local tooling.
"""

import argparse
import hashlib
import json
import re
import socket
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path

import httpx


def main():
    """Run bounded container operations and retain data, logs and a scoped receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="localhost/researcher:modernization")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--podman-command", type=Path)
    options = parser.parse_args()
    prefix = (
        json.loads(options.podman_command.read_text())
        if options.podman_command
        else ["podman"]
    )
    root = options.output.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    data, auth = root / "data", root / "auth"
    data.mkdir(mode=0o700)
    auth.mkdir(mode=0o700)
    name = "researcher-operation-" + uuid.uuid4().hex[:12]
    receipt = {"image": options.image, "model_calls": 0, "native_admission": "not exercised"}
    created = False

    def pod(*arguments, check=True):
        """Wait for the original bounded command and preserve non-secret diagnostics."""
        result = subprocess.run(
            prefix + list(arguments), capture_output=True, text=True, timeout=45
        )
        if check and result.returncode:
            raise RuntimeError(f"Podman {arguments[0]} failed: {result.stderr}")
        return result

    common = [
        "--pull=never", "--userns=keep-id",
        "--mount", f"type=bind,source={data},destination=/data",
    ]

    def wait_ready(url):
        """Poll the same container's HTTP endpoint until ready, terminal or deadline."""
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            state = json.loads(pod("inspect", name).stdout)[0]["State"]
            if not state["Running"]:
                raise RuntimeError(f"Service exited before readiness: {state['ExitCode']}")
            try:
                response = httpx.get(url + "/api/health/ready", timeout=1, trust_env=False)
                if response.status_code == 200 and response.json() == {"ready": True}:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        raise TimeoutError("Original container did not become ready")

    def pair(client):
        """Read only the synthetic service's private code; never write it to receipts."""
        keys = list(auth.glob("owner-*.key"))
        assert len(keys) == 1
        response = client.post(
            "/api/session", json={"code": keys[0].read_text().strip()},
            headers={"X-Researcher-Client": "web"},
        )
        assert response.status_code == 200, response.text
        client.headers["X-Researcher-CSRF"] = response.json()["csrf_token"]

    def stop():
        """Observe graceful service exit and removal of its original owner credential."""
        pod("stop", "--time", "20", name)
        state = json.loads(pod("inspect", name).stdout)[0]["State"]
        assert not state["Running"] and state["ExitCode"] == 143, state
        assert not list(auth.iterdir()), "Owner credential survived normal service shutdown"
        return state["ExitCode"]

    try:
        refused = pod("run", "--rm", "--network=none", *common, options.image,
                      "researcher-start", "--api-only", "--check", check=False)
        assert refused.returncode != 0 and not list(data.iterdir())
        receipt["missing_database_refused_without_creation"] = True
        pod("run", "--rm", "--network=none", *common, options.image,
            "researcher-bootstrap", "init-db", "--database", "/data/infinibay.db")
        db = data / "infinibay.db"
        before = hashlib.sha256(db.read_bytes()).hexdigest()
        refused = pod("run", "--rm", "--network=none", *common, options.image,
                      "researcher-bootstrap", "init-db", "--database", "/data/infinibay.db",
                      check=False)
        assert refused.returncode != 0 and hashlib.sha256(db.read_bytes()).hexdigest() == before
        receipt["existing_database_bootstrap_refused_without_change"] = True
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        pod("run", "-d", "--name", name, "--network=host", *common,
            "--mount", f"type=bind,source={auth},destination=/run/researcher/auth",
            options.image, "researcher-start", "--api-only", "--port", str(port))
        created = True
        wait_ready(url)
        with httpx.Client(base_url=url, timeout=10, trust_env=False) as client:
            assert client.get("/api/projects").status_code == 401
            web = client.get("/")
            assert web.status_code == 200 and '<div id="root">' in web.text
            asset = re.search(r'<script[^>]+src="([^"]+)"', web.text).group(1)
            javascript = client.get(asset)
            assert javascript.status_code == 200 and len(javascript.content) > 1000
            receipt["web_asset_sha256"] = hashlib.sha256(javascript.content).hexdigest()
            pair(client)
            health = client.get("/api/health").json()
            assert health["status"] == "healthy", health
            project = client.post("/api/projects", json={"name": "Image persistence fixture"})
            assert project.status_code == 201, project.text
            project_id = project.json()["id"]
            content = b"Image fixture: original bytes survive a service restart.\n"
            upload = client.post(
                f"/api/files?project_id={project_id}",
                files={"file": ("evidence.txt", content, "text/plain")},
            )
            assert upload.status_code == 201, upload.text
            file_id = upload.json()["id"]
            download = f"/api/files/{file_id}/download?project_id={project_id}"
            assert client.get(download).content == content
            receipt["first_stop_exit_code"] = stop()
            pod("start", name)
            wait_ready(url)
            assert client.get("/api/projects").status_code == 401, "Old owner session survived restart"
            pair(client)
            assert client.get(f"/api/projects/{project_id}").json()["name"] == "Image persistence fixture"
            assert client.get(download).content == content
            assert client.get("/api/health").json()["status"] == "healthy"
            receipt.update(project_id=project_id, file_id=file_id,
                           attachment_sha256=hashlib.sha256(content).hexdigest(),
                           restart_preserves_project_and_attachment=True,
                           restart_requires_new_owner_pairing=True)
            receipt["second_stop_exit_code"] = stop()
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert connection.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 0
        receipt["status"] = "passed"
    except BaseException as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        if created:
            pod("stop", "--time", "20", name, check=False)
            logs = pod("logs", name, check=False)
            (root / "service.log").write_text(logs.stdout + logs.stderr)
            pod("rm", name, check=False)
        (root / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
