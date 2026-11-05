"""Actual TLS smart Git/REST server and owned runtime integration with synthetic account credentials; no external user server or new model inference is used."""

import asyncio
import base64
import json
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

import pytest

from backend.tests.runtime.test_development_session import (
    development_config as development_config,  # noqa: PLC0414 -- actual configured owned author fixture.
)
from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414 -- dependency of development_config.


@pytest.fixture
def tls_remote(tmp_path, socket_enabled):
    """Serve real smart HTTP Git over verified local TLS plus a small controlled Forgejo REST contract; all effect actors are fixture-owned."""
    root = tmp_path / "tls-remote"
    root.mkdir()
    repo = root / "owner/repo.git"
    repo.parent.mkdir()
    subprocess.run(
        ["/usr/bin/git", "init", "--bare", "-q", "--initial-branch=main", str(repo)],
        check=True,
    )
    subprocess.run(
        ["/usr/bin/git", "-C", str(repo), "config", "http.receivepack", "true"],
        check=True,
    )
    key, cert = root / "server.key", root / "server.crt"
    subprocess.run(
        [
            "/usr/bin/openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-sha256",
            "-days",
            "1",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    cert.chmod(0o644)
    token = root / "pat"
    token.write_text("synthetic-owned-forgejo-pat")
    token.chmod(0o600)
    state = SimpleNamespace(
        root=root,
        repo=repo,
        token_file=token,
        token=token.read_text(),
        cert=cert,
        pulls=[],
        git_writes=0,
        posts=[],
        paths=[],
        hold=False,
        entered=threading.Event(),
        release=threading.Event(),
    )
    backend = (
        Path(
            subprocess.check_output(["/usr/bin/git", "--exec-path"], text=True).strip()
        )
        / "git-http-backend"
    )

    def ref(name):
        """Observe fixture refs independently of the application-owned Git clients."""
        return subprocess.check_output(
            ["/usr/bin/git", "-C", str(repo), "rev-parse", "refs/heads/" + name],
            text=True,
        ).strip()

    def pull_record(record):
        """Reflect actual current branch heads while retaining original PR body identity and recorded merge status."""
        result = dict(record)
        result["head"] = {
            "ref": record["head_name"],
            "sha": ref(record["head_name"]),
            "repo": {"id": 71},
        }
        result["base"] = {
            "ref": record["base_name"],
            "sha": ref(record["base_name"]),
            "repo": {"id": 71},
        }
        return result

    class Handler(BaseHTTPRequestHandler):
        """Bounded fixture protocol handler; authentication values are never logged or saved as artifacts."""

        def log_message(self, *_args):
            """Suppress HTTP logs, including query/body/auth diagnostics."""

        def reply(self, status, body=None, headers=None):
            """Send finite actual TLS response bytes without leaving a keepalive worker running."""
            data = b"" if body is None else json.dumps(body).encode()
            self.send_response(status)
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                pass

        def do_GET(self):
            """Route actual Git advertisement and fixed Forgejo read endpoints."""
            self.handle_request()

        def do_POST(self):
            """Route actual receive-pack and controlled PR bookkeeping writes."""
            self.handle_request()

        def handle_request(self):
            """Authenticate by protocol, then execute only this temporary repository or its explicit REST model."""
            parts = urlsplit(self.path)
            path = unquote(parts.path)
            state.paths.append(path)
            api = path.startswith("/api/v1/")
            expected = (
                "token " + state.token
                if api
                else "Basic "
                + base64.b64encode(("fixture-user:" + state.token).encode()).decode()
            )
            if self.headers.get("Authorization") != expected:
                self.reply(401, headers={"WWW-Authenticate": 'Basic realm="fixture"'})
                return
            size = int(self.headers.get("Content-Length", "0"))
            assert size <= 8 * 1024**2
            body = self.rfile.read(size) if size else b""
            if not api:
                if not path.startswith("/owner/repo.git/"):
                    self.reply(404)
                    return
                if self.command == "POST" and path.endswith("/git-receive-pack"):
                    state.git_writes += 1
                    if state.hold:
                        state.entered.set()
                        state.release.wait(20)
                env = {
                    "PATH": "/usr/bin",
                    "GIT_PROJECT_ROOT": str(root),
                    "GIT_HTTP_EXPORT_ALL": "1",
                    "REQUEST_METHOD": self.command,
                    "PATH_INFO": path,
                    "QUERY_STRING": parts.query,
                    "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                    "CONTENT_LENGTH": str(len(body)),
                    "REMOTE_USER": "fixture-user",
                    "HTTP_GIT_PROTOCOL": self.headers.get("Git-Protocol", ""),
                }
                result = subprocess.run(
                    [str(backend)],
                    input=body,
                    env=env,
                    capture_output=True,
                    timeout=20,
                    check=True,
                )
                head, separator, data = result.stdout.partition(b"\r\n\r\n")
                if not separator:
                    head, separator, data = result.stdout.partition(b"\n\n")
                assert separator
                headers = []
                status = 200
                for line in head.decode().splitlines():
                    name, value = line.split(":", 1)
                    if name.lower() == "status":
                        status = int(value.split()[0])
                    else:
                        headers.append((name, value.strip()))
                self.send_response(status)
                for name, value in headers:
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                    pass
                return
            base = "/api/v1/repos/owner/repo"
            if path == base:
                self.reply(
                    200,
                    {
                        "id": 71,
                        "full_name": "owner/repo",
                        "clone_url": state.origin + "/owner/repo.git",
                    },
                )
                return
            if "/branches/" in path:
                self.reply(200, {"commit": {"id": ref(path.split("/branches/", 1)[1])}})
                return
            if path == base + "/pulls" and self.command == "GET":
                self.reply(200, [pull_record(p) for p in state.pulls])
                return
            if path == base + "/pulls" and self.command == "POST":
                payload = json.loads(body)
                state.posts.append("pull")
                record = {
                    "number": len(state.pulls) + 1,
                    "body": payload["body"],
                    "head_name": payload["head"],
                    "base_name": payload["base"],
                    "merged": False,
                }
                state.pulls.append(record)
                self.reply(201, pull_record(record))
                return
            if path.startswith(base + "/pulls/"):
                number = int(path[len(base + "/pulls/") :].split("/")[0])
                record = state.pulls[number - 1]
                if self.command == "GET":
                    self.reply(200, pull_record(record))
                    return
                payload = json.loads(body)
                assert payload["Do"] == "manually-merged" and not payload["force_merge"]
                assert (
                    ref(record["base_name"])
                    == payload["MergeCommitID"]
                    == payload["head_commit_id"]
                )
                state.posts.append("merge")
                record.update(merged=True, merge_commit_sha=payload["MergeCommitID"])
                self.reply(204)
                return
            self.reply(404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    state.origin = "https://127.0.0.1:" + str(server.server_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        state.release.set()
        server.shutdown()
        server.server_close()
        thread.join(3)


@pytest.mark.timeout(300)
async def test_actual_owned_https_push_pr_merge_and_stop_retire_only_local_clients(
    development_config, tls_remote
):
    """The configured owner performs exact Git/REST effects under real TLS, persists stages, keeps secrets out of evidence and retires a blocked original client without claiming server termination."""
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.runtime.code_acceptances import CodeAcceptances
    from backend.runtime.code_publications import (
        CodePublicationIntent,
        CodePublications,
    )
    from backend.runtime.remote_publication import RemoteRepository
    from backend.runtime.remote_runtime import (
        RemoteMergeRequest,
        RemotePublications,
        RemotePullRequest,
        RemotePushRequest,
    )
    from backend.tests.runtime.test_code_acceptance import owner_intent
    from backend.tests.runtime.test_code_review_session import proposed_native_review
    from backend.tests.runtime.test_development_workspace import fixture_git

    c = development_config
    server = tls_remote
    settings = json.loads(c.path.read_text())
    settings["remote_publication"] = {
        "api_base": server.origin + "/api/v1",
        "username": "fixture-user",
        "token_file": str(server.token_file),
        "ca_bundle": str(server.cert),
    }
    c.path.write_text(json.dumps(settings))
    async with proposed_native_review(c) as review:
        await review.session.complete_review()
    runtime, candidate = review.coordinator, review.candidate
    runtime.store.finish(
        review.lease,
        native_status="completed",
        summary="Controlled review before actual HTTPS remote publication",
    )
    owner = CodeAcceptances(runtime.store)
    state = owner.state(101, candidate["run_id"])
    acceptance = owner.accept(101, candidate["run_id"], owner_intent(state))
    local_intent = CodePublicationIntent(
        "owned-local-before-remote",
        acceptance["operation_key"],
        candidate["attempt_id"],
        candidate["context_version"],
        state["subject_sha256"],
        state["review_sha256"],
        "refs/heads/local-accepted",
        None,
    )
    async with runtime:
        local = await runtime.publish_code(101, candidate["run_id"], local_intent)
        await runtime.wait(local.run_id)
        assert runtime.store.get(101, local.run_id).status == "accepted"
        stored = CodePublications(runtime.store).request(101, local.run_id)
        view = stored["view"]
        await fixture_git(server.repo, "fetch", "-q", c.s.workspace, view["base_sha"])
        await fixture_git(
            server.repo, "update-ref", "refs/heads/main", view["base_sha"]
        )
        remote = RemoteRepository(
            server.origin + "/api/v1",
            71,
            "owner/repo",
            server.origin + "/owner/repo.git",
        )
        with runtime.store._transaction(write=True) as conn:
            conn.execute(
                "UPDATE repositories SET remote_url=?WHERE id=?",
                (remote.clone_url, view["source"]["repository_id"]),
            )
            inference_before = conn.execute(
                "SELECT count(*)FROM runtime_inference_dispatches"
            ).fetchone()[0]
        await fixture_git(
            c.s.workspace,
            "config",
            "url." + server.origin + "/wrong/.insteadOf",
            server.origin + "/owner/",
        )
        records = RemotePublications(runtime.store)
        push_request = RemotePushRequest(
            "owned-https-push", local.run_id, remote, "refs/heads/reviewed-change", None
        )
        push = await runtime.publish_remote(101, push_request)
        await runtime.wait(push.run_id)
        assert runtime.store.get(101, push.run_id).status == "accepted", (
            records.request(101, push.run_id)
        )
        assert (await runtime.publish_remote(101, push_request)).run_id == push.run_id
        pull = await runtime.publish_remote(
            101,
            RemotePullRequest(
                "owned-https-pr",
                push.run_id,
                "refs/heads/main",
                view["base_sha"],
                "Reviewed change",
                "Original owner request",
            ),
        )
        await runtime.wait(pull.run_id)
        assert runtime.store.get(101, pull.run_id).status == "accepted", (
            records.request(101, pull.run_id)
        )
        merge = await runtime.publish_remote(
            101, RemoteMergeRequest("owned-https-merge", pull.run_id)
        )
        await runtime.wait(merge.run_id)
        assert runtime.store.get(101, merge.run_id).status == "accepted", (
            records.request(101, merge.run_id)
        )
        assert (
            await fixture_git(server.repo, "rev-parse", "refs/heads/main")
        ).decode().strip() == view["head_sha"]
        assert server.posts == ["pull", "merge"] and server.git_writes == 2
        assert (c.s.workspace / "fact.txt").read_text() == "137"
        assert server.token not in (c.s.workspace / ".git/config").read_text()
        assert not any("/wrong/" in path for path in server.paths)
        server.hold = True
        stopped = await runtime.publish_remote(
            101,
            RemotePushRequest(
                "owned-stop-remote",
                local.run_id,
                remote,
                "refs/heads/stopped-change",
                None,
            ),
        )
        assert await asyncio.to_thread(server.entered.wait, 30)
        await runtime.stop(101, stopped.run_id)
        await runtime.wait(stopped.run_id)
        assert runtime.store.get(101, stopped.run_id).status == "reconciling"
        assert records.request(101, stopped.run_id)["result"] is None
        assert (
            records.request(101, stopped.run_id)["effects"][0]["state"] == "uncertain"
        )
        server.release.set()
        with runtime.store._transaction() as conn:
            assert (
                conn.execute(
                    "SELECT count(*)FROM runtime_inference_dispatches"
                ).fetchone()[0]
                == inference_before
            )
            assert (
                conn.execute(
                    "SELECT count(*)FROM runtime_peers WHERE state!='closed'"
                ).fetchone()[0]
                == 0
            )
        with WitnessedAuthorityJournal(**runtime.runtime.authority) as journal:
            snapshot = journal.load().records
            assert server.token not in json.dumps(snapshot)
            assert snapshot["broker:active"] is None
            remote_ops = [
                v
                for k, v in snapshot.items()
                if k.startswith("broker:op:")
                and v.get("runtime_manifest", {}).get("profile")
                == "owned-remote-git-v1"
            ]
            assert remote_ops and all(op["execution_closed"] for op in remote_ops)
