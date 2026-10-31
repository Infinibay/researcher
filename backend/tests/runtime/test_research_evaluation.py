"""Offline guards for the explicitly invoked live research experiment."""

import json
import subprocess
from pathlib import Path

import pytest

from evals.runtime import run_research as runner


def git(workspace: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(workspace), *args], text=True
    ).strip()


@pytest.fixture
def workspace(tmp_path):
    tmp_path = tmp_path / "workspace"
    tmp_path.mkdir()
    git(tmp_path, "init", "-q")
    (tmp_path / "invoice.py").write_text("original = True\n")
    git(tmp_path, "add", "invoice.py")
    git(
        tmp_path,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@localhost",
        "commit",
        "-qm",
        "Original",
    )
    return tmp_path


def test_research_verifier_allows_only_known_runtime_state(workspace):
    baseline = runner.snapshot_workspace(workspace)
    for name in (".ken", ".infinidev"):
        (workspace / name).mkdir()
        (workspace / name / "state.json").write_text("{}")
    (workspace / ".mcp.json").write_text("{}")
    assert runner.verify_workspace(workspace, baseline)["status"] == "passed"


@pytest.mark.parametrize("mutation", ["edit", "new_file", "empty_commit", "stage_file"])
def test_research_verifier_rejects_unrequested_repository_effects(workspace, mutation):
    baseline = runner.snapshot_workspace(workspace)
    if mutation == "edit":
        (workspace / "invoice.py").write_text("original = False\n")
    elif mutation == "new_file":
        (workspace / "proposal.md").write_text("Unrequested output")
    elif mutation == "stage_file":
        (workspace / "new.py").write_text("Unrequested tracked file")
        git(workspace, "add", "new.py")
    else:
        git(
            workspace,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@localhost",
            "commit",
            "--allow-empty",
            "-qm",
            "Unrequested commit",
        )
    with pytest.raises(AssertionError):
        runner.verify_workspace(workspace, baseline)


@pytest.mark.parametrize(
    "name",
    [
        "researcher_capture_reference",
        "mcp:researcher.researcher_capture_reference",
    ],
)
def test_candidate_permission_accepts_actual_broker_name_and_bridge_name(name):
    pending = {
        "kind": "permission",
        "tool": name,
        "details": json.dumps(
            {
                "effects": ["mutates_external_state"],
                "arguments": {
                    "operation_key": "research-attachment",
                    "reference_file_id": 2,
                },
            }
        ),
    }
    assert runner.infinidev_permission_answer(pending) == "allow"


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("researcher_delete_project", {}),
        ("mcp:other.researcher_capture_reference", {}),
        (
            "researcher_capture_web",
            {"url": "https://other.example", "operation_key": "research-web"},
        ),
        (
            "researcher_capture_reference",
            {"operation_key": "unrequested", "reference_file_id": 2},
        ),
        ("execute_shell", {}),
        ("ken_remember", {}),
    ],
)
def test_candidate_permission_keeps_unrequested_effects_denied(name, arguments):
    pending = {
        "kind": "permission",
        "tool": name,
        "details": json.dumps({"arguments": arguments}),
    }
    assert runner.infinidev_permission_answer(pending) == "deny"


def test_live_candidate_environment_keeps_toolchain_but_not_inherited_credentials(
    monkeypatch,
):
    monkeypatch.setenv("PATH", "/fixture/bin")
    monkeypatch.setenv("CODEX_HOME", "/fixture/codex")
    monkeypatch.setenv("LANG", "es_AR.UTF-8")
    for name in (
        "GITHUB_TOKEN",
        "HF_TOKEN",
        "AWS_SECRET_ACCESS_KEY",
        "HTTP_PROXY",
        "INFINIBAY_DB",
        "INFINIDEV_LLM_BASE_URL",
        "RESEARCHER_TOOL_TOKEN",
    ):
        monkeypatch.setenv(name, "must-not-be-inherited")
    result = runner.environment()
    assert result["PATH"] == "/fixture/bin"
    assert result["CODEX_HOME"] == "/fixture/codex"
    assert result["LANG"] == "es_AR.UTF-8"
    unexpected = [
        name for name, value in result.items() if value == "must-not-be-inherited"
    ]
    assert unexpected == []
