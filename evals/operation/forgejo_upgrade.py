"""Rehearse Forgejo 9 to pinned LTS, verified TLS/Git/PR transport and cold restore.

Only a newly created synthetic output directory is used. No operator account,
repository, Forgejo volume or model is accessed. The real Compose interpolation
is inspected, then its settings are exercised through isolated rootless Podman.
The retained backup is restored into a different directory with the old image;
the upgraded copy and its later writes remain intact for inspection.
"""

import argparse
import asyncio
import base64
import configparser
import hashlib
import json
import os
import secrets
import socket
import ssl
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

import httpx

REPOSITORY = Path(__file__).resolve().parents[2]
BASELINE = "codeberg.org/forgejo/forgejo:9.0.3@sha256:0f07dbf37c585fd0f90b5bb27d66540fd0cf197f5ee79b493be9ee18787797f9"


def main():
    """Keep each original container, cold backup and observed stage tied to this fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compose", default="docker-compose")
    parser.add_argument("--podman-command", type=Path)
    options = parser.parse_args()
    root = options.output.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    data, tls = root / "data", root / "tls"
    data.mkdir(mode=0o755)
    tls.mkdir(mode=0o700)
    prefix = json.loads(options.podman_command.read_text()) if options.podman_command else ["podman"]
    containers = []
    receipt = {"scope": "Synthetic Forgejo service upgrade and native HTTP transport; not full native execution or real-data restore", "stages": [], "model_calls": 0}

    def command(arguments, *, env=None, check=True, timeout=45):
        """Run once with bounded observation and retain stderr without secret arguments."""
        result = subprocess.run(arguments, env=env, capture_output=True, text=True,
                                timeout=timeout, check=False)
        if check and result.returncode:
            raise RuntimeError(f"{Path(arguments[0]).name} failed ({result.returncode}): {result.stderr}")
        return result

    def pod(*arguments, **kwargs):
        """Address only the explicitly selected Podman storage and fixture containers."""
        return command(prefix + list(arguments), **kwargs)

    def stage(name):
        """Persist a completed observation before starting the next dependent phase."""
        receipt["stages"].append(name)
        (root / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(name, flush=True)

    def start(image, directory, environment, phase):
        """Use actual image entrypoint, mapped loopback port and explicit app UID/GID."""
        name = "researcher-forgejo-" + phase + "-" + uuid.uuid4().hex[:8]
        args = ["run", "-d", "--name", name, "--pull=never", "--userns="+service["userns_mode"], "--user="+service["user"],
                "--publish", f"127.0.0.1:{port}:3000",
                "--mount", f"type=bind,source={directory},destination=/data",
                "--mount", f"type=bind,source={tls},destination=/tls,readonly"]
        for key, value in environment.items():
            args.extend(["-e", key + "=" + value])
        pod(*args, image)
        containers.append(name)
        return name

    def ready(name, client, version):
        """Poll one live container; readiness never triggers an automatic replacement."""
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            state = json.loads(pod("inspect", name).stdout)[0]["State"]
            if not state["Running"]:
                raise RuntimeError(f"Original Forgejo exited before readiness: {state['ExitCode']}")
            try:
                response = client.get("/api/v1/version")
                if response.status_code == 200 and response.json()["version"].startswith(version):
                    return response.json()["version"]
            except httpx.TransportError:
                pass
            time.sleep(0.15)
        raise TimeoutError("Original Forgejo did not become ready")

    def stop(name):
        """Flush actual queues, close the service and reject an OOM or forced exit."""
        pod("exec", "--user", "1000", name, "forgejo", "manager", "flush-queues",
            "--config", "/data/gitea/conf/app.ini", "--timeout", "20s")
        pod("stop", "--time", "25", name)
        state = json.loads(pod("inspect", name).stdout)[0]["State"]
        assert not state["Running"] and not state["OOMKilled"] and state["ExitCode"] == 0, state

    def request(client, method, path, expected=200, **kwargs):
        """Assert a real API result without writing credentials or response bodies to logs."""
        response = client.request(method, path, **kwargs)
        assert response.status_code == expected, f"{method} {path}: HTTP {response.status_code}"
        return response.json()

    def wait_refs(client, full_name, expected):
        """Wait only on reads until Forgejo's asynchronous push processing exposes exact refs."""
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            repository = client.get(f"/api/v1/repos/{full_name}")
            branches = client.get(f"/api/v1/repos/{full_name}/branches")
            if repository.status_code == branches.status_code == 200:
                observed = {item["name"]:item["commit"]["id"] for item in branches.json()}
                if repository.json().get("empty") is False and all(observed.get(ref) == sha for ref,sha in expected.items()):
                    return
            time.sleep(0.1)
        raise TimeoutError("Forgejo did not expose the original pushed refs; no PR write was retried")

    def git(*arguments, directory=None, auth=False, secure=False):
        """Use only fixture credentials, explicit CA trust and disabled ambient Git helpers."""
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_COUNT="0")
        config = ["-c", "credential.helper=", "-c", "http.proxy=", "-c", "http.followRedirects=false"]
        if auth:
            env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader",
                       GIT_CONFIG_VALUE_0="Authorization: Basic " + base64.b64encode((username+":"+token).encode()).decode())
        if secure:
            env["GIT_SSL_CAINFO"] = str(tls / "server.crt")
        args = ["git", *config]
        if directory is not None:
            args.extend(["-C", str(directory)])
        return command(args + list(arguments), env=env).stdout.strip()

    try:
        command(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256",
                 "-days", "2", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
                 "-keyout", str(tls/"server.key"), "-out", str(tls/"server.crt")])
        (tls / "server.key").chmod(0o600)
        with socket.socket() as selected:
            selected.bind(("127.0.0.1", 0))
            port = selected.getsockname()[1]
        environment = dict(os.environ, FORGEJO_DATA_DIR=str(data), FORGEJO_TLS_DIR=str(tls), FORGEJO_PORT=str(port))
        config = json.loads(command([options.compose, "-f", str(REPOSITORY/"docker-compose.yml"),
                                     "-f", str(REPOSITORY/"compose.podman.yml"),
                                     "config", "--format", "json"], env=environment).stdout)
        service = config["services"]["forgejo"]
        assert service["userns_mode"] == "keep-id" and service["user"] == "0:0"
        assert service["ports"][0]["host_ip"] == "127.0.0.1"
        assert all(not item["bind"].get("create_host_path", False) for item in service["volumes"])
        target = service["image"]
        modern_env = service["environment"]
        old_env = {k:v for k,v in modern_env.items() if k not in (
            "FORGEJO__server__CERT_FILE", "FORGEJO__server__KEY_FILE")}
        old_env.update(FORGEJO__server__PROTOCOL="http", FORGEJO__server__ROOT_URL=f"http://127.0.0.1:{port}/")
        receipt.update(baseline_image=BASELINE, target_image=target, compose_loopback=True,
                       compose_existing_bind_directories_required=True)
        username, password = "upgrade-owner", secrets.token_urlsafe(30)
        baseline = start(BASELINE, data, old_env, "baseline")
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5, trust_env=False) as client:
            receipt["baseline_version"] = ready(baseline, client, "9.0.3")
            users = pod("exec", "--user", "1000", baseline, "forgejo", "admin", "user", "list",
                        "--config", "/data/gitea/conf/app.ini").stdout
            assert username not in users
            pod("exec", "--user", "1000", baseline, "forgejo", "admin", "user", "create",
                "--config", "/data/gitea/conf/app.ini", "--username", username, "--password", password,
                "--email", "upgrade@example.invalid", "--admin", "--must-change-password=false")
            restricted = request(client, "POST", f"/api/v1/users/{username}/tokens", expected=201,
                                 auth=(username,password), json={"name":"restricted-fixture", "scopes":["write:repository","read:user"]})["sha1"]
            denied = client.post("/api/v1/user/repos", headers={"Authorization":"token "+restricted},
                                 json={"name":"upgrade-fixture", "private":True, "auto_init":False})
            assert denied.status_code == 403
            assert client.get(f"/api/v1/repos/{username}/upgrade-fixture",
                              headers={"Authorization":"token "+restricted}).status_code == 404
            receipt["creation_requires_write_user_scope"] = True
            token = request(client, "POST", f"/api/v1/users/{username}/tokens", expected=201,
                            auth=(username,password), json={"name":"upgrade-fixture", "scopes":["write:repository","write:user"]})["sha1"]
            client.headers["Authorization"] = "token " + token
            repo = request(client, "POST", "/api/v1/user/repos", expected=201,
                           json={"name":"upgrade-fixture", "private":True, "auto_init":False, "default_branch":"main"})
            full_name = repo["full_name"]
            checkout = root / "old-checkout"
            git("clone", repo["clone_url"], str(checkout), auth=True)
            git("checkout", "-b", "main", directory=checkout)
            (checkout/"README.md").write_text("Original Forgejo 9 fixture\n")
            git("add", "README.md", directory=checkout)
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Original baseline", directory=checkout)
            main_sha = git("rev-parse", "HEAD", directory=checkout)
            git("push", "origin", "main", directory=checkout, auth=True)
            git("checkout", "-b", "pre-upgrade", directory=checkout)
            (checkout/"evidence.txt").write_text("Keep this branch and its pull request.\n")
            git("add", "evidence.txt", directory=checkout)
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Retained branch", directory=checkout)
            branch_sha = git("rev-parse", "HEAD", directory=checkout)
            git("push", "origin", "pre-upgrade", directory=checkout, auth=True)
            wait_refs(client, full_name, {"main":main_sha, "pre-upgrade":branch_sha})
            pull = request(client, "POST", f"/api/v1/repos/{full_name}/pulls", expected=201,
                           json={"base":"main", "head":"pre-upgrade", "title":"Retain this PR", "body":"Original evidence"})
            receipt.update(repository_id=repo["id"], original_main=main_sha, original_branch=branch_sha, original_pull=pull["number"])
        stop(baseline)
        stage("Forgejo 9 authenticated clone/push/PR and graceful cold stop passed")
        archive = root / "pre-upgrade.tar"
        pod("unshare", "tar", "--numeric-owner", "-cpf", str(archive), "-C", str(data), ".")
        archive.chmod(0o600)
        receipt["cold_backup_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        stage("Complete stopped data volume archived")

        upgraded = start(target, data, modern_env, "upgraded")
        context = ssl.create_default_context(cafile=str(tls/"server.crt"))
        url = f"https://127.0.0.1:{port}"
        with httpx.Client(base_url=url, verify=context, timeout=5, trust_env=False,
                          headers={"Authorization":"token "+token}) as client:
            receipt["upgraded_version"] = ready(upgraded, client, "15.0.11")
            assert request(client, "GET", "/api/v1/user")["login"] == username
            denied = client.post("/api/v1/user/repos", headers={"Authorization":"token "+restricted},
                                 json={"name":"forbidden-after-upgrade", "private":True, "auto_init":False})
            assert denied.status_code == 403
            assert client.get(f"/api/v1/repos/{username}/forbidden-after-upgrade").status_code == 404
            receipt["restricted_token_scope_preserved_after_upgrade"] = True
            retained = request(client, "GET", f"/api/v1/repos/{full_name}/pulls/{pull['number']}")
            assert retained["body"] == "Original evidence" and retained["head"]["sha"] == branch_sha
            current = request(client, "GET", f"/api/v1/repos/{full_name}")
            assert current["id"] == repo["id"] and current["clone_url"] == url+"/"+full_name+".git"
            fresh = root / "tls-checkout"
            git("clone", current["clone_url"], str(fresh), auth=True, secure=True)
            assert git("rev-parse", "HEAD", directory=fresh) == main_sha
            git("checkout", "-b", "native-proof", directory=fresh)
            (fresh/"native.txt").write_text("Native transport over verified TLS\n")
            git("add", "native.txt", directory=fresh)
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Native TLS proof", directory=fresh)
            candidate = git("rev-parse", "HEAD", directory=fresh)
            git("push", "origin", "native-proof", directory=fresh, auth=True, secure=True)
            wait_refs(client, full_name, {"main":main_sha, "native-proof":candidate})

            async def native_pull():
                """Use the real product PR transport, then reconcile only after its actual close."""
                sys.path.insert(0, str(REPOSITORY))
                from backend.runtime.forgejo_publication import ForgejoPublicationClient, RemotePullIntent
                from backend.runtime.remote_publication import RemoteRepository
                remote = RemoteRepository(url+"/api/v1", repo["id"], full_name, current["clone_url"])
                intent = RemotePullIntent("forgejo-upgrade-fixture", remote, "refs/heads/native-proof",
                                          "refs/heads/main", candidate, main_sha, "Native TLS proof", "Original native receipt")
                async with ForgejoPublicationClient(remote.api_base, token, verify=context) as transport:
                    created = await transport.create_pull(intent)
                async with ForgejoPublicationClient(remote.api_base, token, verify=context) as observer:
                    observed = await observer.reconcile_pull(intent, original_client_closed=True)
                assert observed == created and created.candidate_current
                return asdict(created)

            receipt["native_pull"] = asyncio.run(native_pull())
            invalid = client.get("/api/v1/user", headers={"Authorization":"token invalid-fixture-token"})
            assert invalid.status_code == 401
        doctor = pod("exec", "--user", "1000", upgraded, "forgejo", "doctor", "check", "--all",
                     "--config", "/data/gitea/conf/app.ini", "--log-file", "-", check=False)
        (root/"doctor.log").write_text(doctor.stdout+doctor.stderr)
        assert doctor.returncode == 0, "Forgejo doctor reported errors; inspect doctor.log"
        active = configparser.ConfigParser(interpolation=None)
        active.read_string("[DEFAULT]\n" + (data/"gitea/conf/app.ini").read_text())
        assert active.get("server", "PROTOCOL") == "https"
        assert active.get("security", "REVERSE_PROXY_TRUSTED_PROXIES") != "*"
        assert not active.getboolean("service", "ENABLE_REVERSE_PROXY_AUTHENTICATION")
        receipt["doctor_exit_code"] = doctor.returncode
        receipt["tls_and_proxy_settings_observed"] = True
        stop(upgraded)
        stage("Forgejo 15 migration, verified TLS clone/push/native PR reconciliation and doctor passed")

        restored = root / "restored-elsewhere"
        restored.mkdir(mode=0o755)
        pod("unshare", "tar", "--numeric-owner", "-xpf", str(archive), "-C", str(restored))
        pod("unshare", "tar", "--compare", "-f", str(archive), "-C", str(restored))
        restored_service = start(BASELINE, restored, old_env, "restored")
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5, trust_env=False,
                          headers={"Authorization":"token "+token}) as client:
            receipt["restored_version"] = ready(restored_service, client, "9.0.3")
            original = request(client, "GET", f"/api/v1/repos/{full_name}/pulls/{pull['number']}")
            assert original["head"]["sha"] == branch_sha and original["body"] == "Original evidence"
            restored_repo = request(client, "GET", f"/api/v1/repos/{full_name}")
            assert restored_repo["id"] == repo["id"]
            restored_checkout = root / "restored-checkout"
            git("clone", restored_repo["clone_url"], str(restored_checkout), auth=True)
            assert git("rev-parse", "HEAD", directory=restored_checkout) == main_sha
            assert git("rev-parse", "origin/pre-upgrade", directory=restored_checkout) == branch_sha
            missing = client.get(f"/api/v1/repos/{full_name}/pulls/{receipt['native_pull']['number']}")
            assert missing.status_code == 404, "Old backup unexpectedly contains later writes"
        stop(restored_service)
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == receipt["cold_backup_sha256"]
        receipt.update(restored_in_different_directory=True, restored_archive_bytes_verified=True,
                       restored_original_account_token_refs_and_pull=True,
                       upgraded_copy_retained=True, later_writes_not_in_old_backup=True, status="passed")
        stage("Old backup restored elsewhere; original identity/history retained and later writes explicitly absent")
    except BaseException as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        for name in containers:
            pod("stop", "--time", "25", name, check=False)
            logs = pod("logs", name, check=False)
            (root/(name+".log")).write_text(logs.stdout+logs.stderr)
            pod("rm", name, check=False)
        (root/"result.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt,indent=2))


if __name__ == "__main__":
    main()
