"""Old selected bytes are owner-chosen data, not invented native authorship, Git history or execution authority."""

import base64
import os
from dataclasses import replace
from pathlib import Path

import pytest

from backend.runtime.contracts import InputTooLarge, RunConflict, RunNotFound


@pytest.fixture
def legacy_files(service_setup):
    """Record a real directory with a legacy Git pointer; no native execution or historic task ownership is fabricated."""
    from backend.runtime.workspaces import WorkspaceRegistry

    s = service_setup
    s.c.conn.execute("UPDATE tasks SET type='code' WHERE id=1001")
    root = s.workspace / ".worktrees" / "old-developer"
    root.mkdir(parents=True)
    (root / ".git").write_text("gitdir: ../../.git/worktrees/old-developer\n")
    (root / "fact.txt").write_text("200")
    (root / "binary.bin").write_bytes(b"\0\xffold")
    (root / "run.sh").write_text("echo old\n")
    (root / "run.sh").chmod(0o755)
    (root / "link").symlink_to("fact.txt")
    s.c.conn.execute(
        "INSERT INTO agent_worktrees(id,project_id,repo_id,agent_id,worktree_path,branch_name) VALUES(7,101,11,'old-developer',?,'worktree/old-developer')",
        (str(root),),
    )
    s.c.conn.commit()
    binding = WorkspaceRegistry(s.c.database, s.root).bind(101, 11)
    return s, root, binding


def test_selected_legacy_paths_preserve_bytes_mode_link_and_absence_without_guessing_context(
    legacy_files,
):
    """Following Git pointers or inventing a historic task mapping would import credentials or attribute unrelated work."""
    from backend.runtime.file_imports import FileImports

    s, root, binding = legacy_files
    packet = FileImports(s.c.store).preview(
        101,
        1001,
        binding,
        "legacy_worktree",
        "7",
        ("fact.txt", "binary.bin", "run.sh", "link", "removed.txt"),
    )
    data = packet["snapshot"]
    assert data["origin"]["kind"] == "selected_legacy_worktree_files"
    assert (
        data["origin"]["task_relation"] == "selected_by_owner_not_historically_verified"
    )
    assert data["original_input"] is None
    assert data["git_ancestry"] == "not_inspected"
    entries = {item["path"]: item for item in data["files"]}
    assert base64.b64decode(entries["fact.txt"]["content_base64"]) == b"200"
    assert base64.b64decode(entries["binary.bin"]["content_base64"]) == b"\0\xffold"
    assert entries["run.sh"]["git_mode"] == "100755"
    assert base64.b64decode(entries["link"]["target_base64"]) == b"fact.txt"
    assert entries["removed.txt"]["kind"] == "missing"
    assert data["selection_scope"] == "selected_paths_only"
    assert packet["authority"] == "data_only" and packet["acceptance"] == "not_granted"
    assert (root / "fact.txt").read_text() == "200" and not (
        root / "removed.txt"
    ).exists()
    assert s.c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 0


def test_admission_keeps_exact_import_after_source_loss_and_rejects_changed_selection(
    legacy_files,
):
    """Re-reading old live files on retry would lose the selected material or silently change a committed request."""
    from backend.runtime.code_carryover import CodeCarryovers
    from backend.runtime.file_imports import FileImports, PriorFilesTarget

    s, root, binding = legacy_files
    imports = FileImports(s.c.store)
    paths = ("fact.txt",)
    preview = imports.preview(101, 1001, binding, "legacy_worktree", "7", paths)
    target = PriorFilesTarget("legacy_worktree", "7", paths, preview["snapshot_sha256"])
    spec = replace(
        s.c.spec,
        context_version=s.c.store.context_snapshot(101, 1001)["context_version"],
        operation_key="import-old",
        prompt="Use these selected earlier files; adapt them to the current request.",
    )
    (root / "fact.txt").write_text("201")
    with pytest.raises(RunConflict):
        s.c.store.admit_once(spec, binding=binding, prior_code=target)
    assert not s.c.store.task_runs(101, 1001)
    preview = imports.preview(101, 1001, binding, "legacy_worktree", "7", paths)
    target = replace(target, snapshot_sha256=preview["snapshot_sha256"])
    run, created = s.c.store.admit_once(spec, binding=binding, prior_code=target)
    assert created and run.execution_kind == "development" and run.attempt_id is None
    (root / "fact.txt").unlink()
    assert s.c.store.admit_once(spec, binding=binding, prior_code=target) == (
        run,
        False,
    )
    with s.c.store._transaction() as conn:
        saved = CodeCarryovers.input(conn, s.c.store._row(conn, 101, run.run_id))
    assert base64.b64decode(saved["snapshot"]["files"][0]["content_base64"]) == b"201"
    assert saved["snapshot"]["original_input"] is None
    with pytest.raises(RunConflict):
        s.c.store.admit_once(
            spec, binding=binding, prior_code=replace(target, paths=("binary.bin",))
        )


@pytest.mark.parametrize(
    "path",
    ["../fact.txt", "/etc/passwd", ".git", ".ken/token", "dir/.git/config", "a//b"],
)
def test_metadata_and_noncanonical_paths_are_not_exported(legacy_files, path):
    """An explicit file selector must not expand into metadata, credentials or paths outside its registered directory."""
    from backend.runtime.file_imports import FileImports

    s, _root, binding = legacy_files
    with pytest.raises((ValueError, RunConflict)):
        FileImports(s.c.store).preview(
            101, 1001, binding, "legacy_worktree", "7", (path,)
        )


@pytest.mark.parametrize(
    "fault",
    [
        "parent_symlink",
        "fifo",
        "oversize",
        "foreign_project",
        "foreign_repository",
        "redirected_registration",
    ],
)
def test_unavailable_unsafe_or_foreign_sources_never_become_new_author_input(
    legacy_files, fault
):
    """The export must refuse unsafe reads and foreign origin before storing any request or mutating original data."""
    from backend.runtime.file_imports import FileImports

    s, root, binding = legacy_files
    paths = ("fact.txt",)
    project = 101
    if fault == "parent_symlink":
        outside = s.root / "elsewhere"
        outside.mkdir()
        (outside / "fact.txt").write_text("foreign bytes")
        (root / "outside").symlink_to(outside)
        paths = ("outside/fact.txt",)
    elif fault == "fifo":
        os.mkfifo(root / "fifo")
        paths = ("fifo",)
    elif fault == "oversize":
        (root / "huge").write_bytes(b"x" * 500000)
        paths = ("huge",)
    elif fault == "foreign_project":
        project = 202
    elif fault == "foreign_repository":
        binding = replace(binding, repository_id=12, requested_repository_id=None)
    else:
        s.c.conn.execute(
            "UPDATE agent_worktrees SET worktree_path=? WHERE id=7", (str(s.workspace),)
        )
        s.c.conn.commit()
    with pytest.raises((RunConflict, RunNotFound, InputTooLarge)):
        FileImports(s.c.store).preview(
            project, 1001, binding, "legacy_worktree", "7", paths
        )
    assert s.c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 0
    assert (root / "fact.txt").read_text() == "200"


def test_uncaptured_private_copy_remains_data_with_unknown_original_input(
    service_setup,
):
    """Missing native context must not destroy recoverable private bytes or be replaced by current requirements."""
    from backend.runtime.development_state import DevelopmentWorkspaces
    from backend.runtime.file_imports import FileImports
    from backend.runtime.workspaces import WorkspaceRegistry

    s = service_setup
    s.c.conn.execute("UPDATE tasks SET type='code' WHERE id=1001")
    s.c.conn.commit()
    binding = WorkspaceRegistry(s.c.database, s.root).bind(101, 11)
    spec = replace(
        s.c.spec,
        context_version=s.c.store.context_snapshot(101, 1001)["context_version"],
    )
    run = s.c.store.admit(spec, binding=binding)
    lease = s.c.store.claim(101, run.run_id, "old-host")
    control = s.control / "development"
    control.mkdir(mode=0o700, parents=True)
    planned, _ = DevelopmentWorkspaces(s.c.store, control).plan(lease)
    copy = Path(planned["allocation"]) / "repository"
    copy.mkdir(parents=True)
    (copy / "fact.txt").write_text("201")
    packet = FileImports(s.c.store).preview(
        101, 1001, binding, "private_copy", lease.attempt_id, ("fact.txt",)
    )
    assert packet["snapshot"]["original_input"] is None
    assert packet["snapshot"]["origin"]["kind"] == "selected_private_copy_files"
    assert base64.b64decode(packet["snapshot"]["files"][0]["content_base64"]) == b"201"
    assert s.c.store.get(101, run.run_id).status == "running"


async def test_owner_can_preview_and_admit_selected_legacy_data_through_http_and_chat(
    legacy_files,
):
    """A label or client-supplied origin cannot replace the scoped source packet at either owner entry."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.runtime.code_carryover import CodeCarryovers
    from backend.tests.runtime.test_runtime_service import (
        ControlledInference,
        coordinator,
    )
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s, root, _binding = legacy_files
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters")
    )
    inference = ControlledInference(s)
    inference.supported_task_types = ("research", "code", "bug_fix")
    async with (
        app.router.lifespan_context(app),
        coordinator(s, inference, legacy_active=lambda _project: True) as runtime,
    ):
        app.state.runtime_service = runtime
        async with owner_client(app) as owner:
            base = "/api/projects/101/tasks/1001"
            listed = await owner.get(base + "/prior-files/sources")
            assert listed.status_code == 200, listed.text
            assert listed.json()[0]["source_id"] == "7"
            selection = {
                "source_kind": "legacy_worktree",
                "source_id": "7",
                "paths": ["fact.txt"],
                "repository_id": 11,
            }
            preview = await owner.post(base + "/prior-files/preview", json=selection)
            assert preview.status_code == 200, preview.text
            assert (
                await owner.post(
                    base + "/prior-files/preview", json={**selection, "paths": [".git"]}
                )
            ).status_code == 422
            target = {
                key: value for key, value in selection.items() if key != "repository_id"
            }
            target["snapshot_sha256"] = preview.json()["snapshot_sha256"]
            version = s.c.store.context_snapshot(101, 1001)["context_version"]
            body = {
                "operation_key": "owner-file-import",
                "context_version": version,
                "request": "Use these older selected bytes as data.",
                "repository_id": 11,
                "prior_code": target,
            }
            admitted = await owner.post(base + "/runs", json=body)
            assert admitted.status_code == 202, admitted.text
            run = admitted.json()
            (root / "fact.txt").write_text("changed later")
            replay = await owner.post(base + "/runs", json=body)
            assert (
                replay.status_code == 202 and replay.json()["run_id"] == run["run_id"]
            )
            with s.c.store._transaction() as conn:
                saved = CodeCarryovers.input(
                    conn, s.c.store._row(conn, 101, run["run_id"])
                )
            assert (
                base64.b64decode(saved["snapshot"]["files"][0]["content_base64"])
                == b"200"
            )
            await runtime.stop(101, run["run_id"])
            fresh = await owner.post(base + "/prior-files/preview", json=selection)
            target["snapshot_sha256"] = fresh.json()["snapshot_sha256"]
            response = await owner.post(
                "/api/chat/101/instructions",
                json={
                    "task_id": 1001,
                    "operation_key": "chat-file-import",
                    "context_version": version,
                    "message": "Inspect and adapt these selected files.",
                    "thread_id": "import-thread",
                    "repository_id": 11,
                    "prior_code": target,
                },
            )
            assert response.status_code == 202, response.text
            assert (
                response.json()["message"]["message"]
                == "Inspect and adapt these selected files."
            )
            assert inference.prompts == []


def test_controlled_author_fixture_applies_the_delivered_bytes_instead_of_repeating_a_hardcoded_edit(
    tmp_path,
):
    """Validate the changed fixture contract cheaply before launching its long kernel/Git integration."""
    import ast
    import json
    import subprocess
    import sys

    tree = ast.parse(Path(__file__).with_name("fake_owned_native.py").read_text())
    definition = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "development_edit_code"
    )
    files = [
        {
            "path": "fact.txt",
            "kind": "file",
            "content_base64": base64.b64encode(b"217").decode(),
            "git_mode": "100644",
        },
        {
            "path": "binary.bin",
            "kind": "file",
            "content_base64": base64.b64encode(b"\0\xffold").decode(),
            "git_mode": "100755",
        },
    ]
    namespace = {"json": json, "prior_code_patch": None, "prior_selected_files": files}
    exec(  # noqa: S102 -- Compile trusted fixture definitions only, never imported user data.
        compile(
            ast.Module(body=[definition], type_ignores=[]),
            "controlled-author-fixture",
            "exec",
        ),
        namespace,
    )
    (tmp_path / "fact.txt").write_text("137")
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", namespace["development_edit_code"]()],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    assert (tmp_path / "fact.txt").read_bytes() == b"217"
    assert (tmp_path / "binary.bin").read_bytes() == b"\0\xffold"
    assert (tmp_path / "binary.bin").stat().st_mode & 0o777 == 0o755
    assert b"selected old files applied" in result.stdout
    review = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "next_code_review_tool"
    )
    calls = []

    def record_call(name, arguments):
        """Observe the controlled reviewer advancing beyond unknown original input without opening any real tool."""
        calls.append((name, arguments))

    namespace = {
        "json": json,
        "steps": 3,
        "code_packet": {
            "text": json.dumps({"author_request": {"source_kind": "owner_admission"}})
        },
        "code_prior_files": False,
        "call": record_call,
    }
    exec(  # noqa: S102 -- Compile trusted fixture definitions only, never imported user data.
        compile(
            ast.Module(body=[review], type_ignores=[]),
            "controlled-reviewer-fixture",
            "exec",
        ),
        namespace,
    )
    author_input = {
        "request": "Import selected older files into a fresh copy.",
        "prior_code": {
            "snapshot": {
                "files": files,
                "original_input": None,
                "original_input_status": "unknown",
                "origin": {
                    "task_relation": "selected_by_owner_not_historically_verified"
                },
            }
        },
    }
    namespace["next_code_review_tool"](
        {
            "success": True,
            "contentItems": [
                {
                    "text": json.dumps(
                        {"complete_material": True, "text": json.dumps(author_input)}
                    )
                }
            ],
        }
    )
    assert namespace["code_prior_files"] is True
    assert calls == [
        ("researcher_code_review_subject", {"section": "diff", "max_chars": 24000})
    ]
