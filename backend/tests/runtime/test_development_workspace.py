"""Real Git preparation must isolate one attempt without credentials, branch reset or source edits."""

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest


async def fixture_git(directory, *arguments):
    """Run synthetic fixture Git outside the event loop; this helper never runs product or model code."""
    return await asyncio.to_thread(
        subprocess.check_output, ["git", "-C", str(directory), *arguments]
    )


@pytest.fixture
def source_repository(tmp_path):
    """Create a committed synthetic source and a binding with no model/account connection."""
    from backend.runtime.contracts import WorkspaceBinding

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "value.py").write_text(
        '"""Synthetic development fixture."""\nVALUE = 137\n'
    )
    subprocess.run(["git", "-C", str(source), "add", "value.py"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@localhost",
            "commit",
            "-qm",
            "base",
        ],
        check=True,
    )
    info = source.stat()
    binding = WorkspaceBinding(
        11, "fixture", str(source), str(source), info.st_dev, info.st_ino
    )
    return source, binding


class RealGitExecutor:
    """Test-only subprocess owner for trusted Git on synthetic data, never the production runtime executor."""

    git_binary = Path(shutil.which("git")).resolve(strict=True)

    def execution_path(self, host_path):
        """The synthetic host-only executor uses identity path mapping."""
        return Path(host_path)

    async def run(self, command, *, cwd, env, timeout):
        """Execute actual Git with the supplied clean environment and close its process on failure."""
        from backend.runtime.development_workspace import GitResult

        assert not any(
            "OPENAI" in key or key.startswith("GIT_CONFIG_COUNT") for key in env
        )
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        except BaseException:
            process.kill()
            await process.wait()
            raise
        if process.returncode:
            raise RuntimeError(stderr.decode(errors="replace")[:1000])
        return GitResult(stdout, process.returncode, True, True)


async def test_prepared_copy_has_exact_base_and_no_source_auth_or_remotes(
    source_repository, tmp_path, monkeypatch
):
    """A real detached independent copy cannot inherit source config or redirect the source checkout."""
    from backend.runtime.development_workspace import prepare_workspace

    source, binding = source_repository
    await fixture_git(
        source, "config", "http.extraHeader", "Authorization: SYNTHETIC-SOURCE-ONLY"
    )
    global_config = tmp_path / "host.gitconfig"
    global_config.write_text(
        "[credential]\n helper = synthetic-host-helper\n[http]\n extraHeader = SYNTHETIC-HOST-ONLY\n"
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC-NOT-A-REAL-KEY")
    destination = tmp_path / "private" / "attempt-1"
    destination.parent.mkdir(mode=0o700)
    prepared = await prepare_workspace(binding, destination, executor=RealGitExecutor())
    original = (await fixture_git(source, "rev-parse", "HEAD")).decode().strip()
    assert prepared.base_sha == original
    working = Path(prepared.workspace)
    assert working == destination / "repository"
    assert working.stat().st_mode & 0o077 == 0
    assert (working / "value.py").read_bytes() == (source / "value.py").read_bytes()
    config = (working / ".git" / "config").read_text()
    assert (
        "SYNTHETIC" not in config
        and "extraHeader" not in config
        and "synthetic-host-helper" not in config
    )
    assert (await fixture_git(working, "remote")) == b""
    assert not (working / ".git/objects/info/alternates").exists()
    (working / "value.py").write_text("VALUE = 200\n")
    assert "137" in (source / "value.py").read_text()
    assert (await fixture_git(source, "status", "--porcelain")) == b""
    assert (
        prepared.device == working.stat().st_dev
        and prepared.inode == working.stat().st_ino
    )


@pytest.mark.parametrize("dirty", ["tracked", "untracked"])
async def test_dirty_source_is_retained_and_not_silently_adopted(
    source_repository, tmp_path, dirty
):
    """Preparation cannot silently attribute previous user edits to a newly admitted attempt."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.development_workspace import prepare_workspace

    source, binding = source_repository
    target = source / ("value.py" if dirty == "tracked" else "pending.txt")
    target.write_text("Uncommitted work must survive.\n")
    destination = tmp_path / "attempt"
    with pytest.raises(RunConflict, match="uncommitted"):
        await prepare_workspace(binding, destination, executor=RealGitExecutor())
    assert target.read_text() == "Uncommitted work must survive.\n"
    assert not destination.exists()


async def test_untracked_legacy_worktrees_survive_and_are_not_copied_into_the_native_base(
    source_repository, tmp_path
):
    """Treating old per-agent directories as dirty code would make real file import impossible without editing the original ignore rules."""
    from backend.runtime.development_workspace import prepare_workspace

    source, binding = source_repository
    old = source / ".worktrees" / "old-developer"
    await fixture_git(source, "worktree", "add", "--detach", str(old), "HEAD")
    (old / "value.py").write_text("VALUE = 200\n")
    prepared = await prepare_workspace(
        binding, tmp_path / "new-attempt", executor=RealGitExecutor()
    )
    assert "137" in (Path(prepared.workspace) / "value.py").read_text()
    assert not (Path(prepared.workspace) / ".worktrees").exists()
    assert (old / "value.py").read_text() == "VALUE = 200\n"
    assert (old / ".git").is_file()
    assert await fixture_git(source, "status", "--porcelain", "--", "value.py") == b""


@pytest.mark.parametrize(
    "case", ["tracked_reserved", "staged_reserved", "untracked_lookalike"]
)
async def test_legacy_storage_exclusion_does_not_hide_tracked_or_lookalike_code(
    source_repository, tmp_path, case
):
    """Only the untracked reserved namespace may survive outside the clone; actual code changes still block admission."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.development_workspace import prepare_workspace

    source, binding = source_repository
    folder = source / (
        ".worktrees"
        if case in ("tracked_reserved", "staged_reserved")
        else ".worktrees-other"
    )
    folder.mkdir()
    (folder / "pending.py").write_text("VALUE = 200\n")
    if case in ("tracked_reserved", "staged_reserved"):
        await fixture_git(source, "add", ".worktrees/pending.py")
    if case == "tracked_reserved":
        await fixture_git(
            source,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@localhost",
            "commit",
            "-qm",
            "tracked reserved source",
        )
    with pytest.raises(RunConflict):
        await prepare_workspace(
            binding, tmp_path / "new-attempt", executor=RealGitExecutor()
        )
    assert (folder / "pending.py").read_text() == "VALUE = 200\n"


async def test_existing_attempt_directory_is_never_reset_or_removed(
    source_repository, tmp_path
):
    """A resumed/crashed allocation requires reconciliation rather than destructive recreation."""
    from backend.runtime.development_workspace import prepare_workspace

    _, binding = source_repository
    destination = tmp_path / "attempt"
    destination.mkdir()
    (destination / "unfinished.txt").write_text("Keep this result.")
    with pytest.raises(FileExistsError):
        await prepare_workspace(binding, destination, executor=RealGitExecutor())
    assert (destination / "unfinished.txt").read_text() == "Keep this result."


async def test_repository_tree_larger_than_command_preview_is_prepared_completely(
    source_repository, tmp_path
):
    """A realistic tree cannot be rejected or silently truncated at a command-output preview boundary."""
    from backend.runtime.development_workspace import prepare_workspace

    source, binding = source_repository
    folder = source / "modules"
    folder.mkdir()
    for index in range(900):
        (
            folder / (f"module_{index:04d}_" + "descriptive_name_" * 4 + ".py")
        ).write_text("VALUE = 137\n")
    await fixture_git(source, "add", "modules")
    await fixture_git(
        source,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@localhost",
        "commit",
        "-qm",
        "many files",
    )
    prepared = await prepare_workspace(
        binding, tmp_path / "large-attempt", executor=RealGitExecutor()
    )
    assert len(list((Path(prepared.workspace) / "modules").glob("*.py"))) == 900


@pytest.mark.parametrize("complete,closed", [(False, True), (True, False)])
async def test_unconfirmed_execution_or_partial_output_cannot_produce_workspace_receipt(
    source_repository, tmp_path, complete, closed
):
    """Git-looking bytes alone do not prove command completion or physical process closure."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.development_workspace import GitResult, prepare_workspace

    class Unconfirmed(RealGitExecutor):
        """Supply incomplete owner evidence without launching any command."""

        async def run(self, command, *, cwd, env, timeout):
            """Return explicit uncertainty rather than an invented successful process."""
            return GitResult(b"a" * 40 + b"\n", 0, complete, closed)

    _, binding = source_repository
    destination = tmp_path / "attempt"
    with pytest.raises(RunConflict, match="unconfirmed"):
        await prepare_workspace(binding, destination, executor=Unconfirmed())
    assert not destination.exists()


async def test_failure_after_clone_retains_copy_and_refuses_destructive_retry(
    source_repository, tmp_path
):
    """A failed later preparation step leaves recoverable files rather than resetting a reused path."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.development_workspace import prepare_workspace

    class LoseCloneResponse(RealGitExecutor):
        """Exercise a real completed clone followed by a lost owner-side observation."""

        async def run(self, command, *, cwd, env, timeout):
            """Retain the completed effect before reporting an uncertain response."""
            result = await super().run(command, cwd=cwd, env=env, timeout=timeout)
            if "clone" in command:
                raise RuntimeError("Synthetic lost clone response")
            return result

    source, binding = source_repository
    destination = tmp_path / "retained"
    with pytest.raises(RunConflict):
        await prepare_workspace(binding, destination, executor=LoseCloneResponse())
    repository = destination / "repository"
    retained = repository / ".git/HEAD"
    assert (await fixture_git(repository, "show", "HEAD:value.py")) == (
        source / "value.py"
    ).read_bytes()
    with pytest.raises(FileExistsError):
        await prepare_workspace(binding, destination, executor=RealGitExecutor())
    assert retained.exists()


async def test_hidden_index_edits_are_preserved_instead_of_silently_adopted(
    source_repository, tmp_path
):
    """Assume-unchanged index flags cannot hide prior user work from the preparation precondition."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.development_workspace import prepare_workspace

    source, binding = source_repository
    await fixture_git(source, "update-index", "--assume-unchanged", "value.py")
    (source / "value.py").write_text("VALUE = 999\n")
    with pytest.raises(RunConflict, match="index hides"):
        await prepare_workspace(
            binding, tmp_path / "attempt", executor=RealGitExecutor()
        )
    assert (source / "value.py").read_text() == "VALUE = 999\n"


async def test_source_clean_filters_cannot_execute_during_preflight(
    source_repository, tmp_path
):
    """Reading source status must not run arbitrary repository-configured code on the host executor."""
    import shlex

    from backend.runtime.contracts import RunConflict
    from backend.runtime.development_workspace import prepare_workspace

    source, binding = source_repository
    (source / ".gitattributes").write_text("value.py filter=fixtureDanger\n")
    await fixture_git(source, "add", ".gitattributes")
    await fixture_git(
        source,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@localhost",
        "commit",
        "-qm",
        "attributes",
    )
    marker = tmp_path / "unexpected-filter-ran"
    await fixture_git(
        source,
        "config",
        "filter.fixtureDanger.clean",
        "touch " + shlex.quote(str(marker)) + "; cat",
    )
    (source / "value.py").write_text((source / "value.py").read_text())
    with pytest.raises(RunConflict, match="filters"):
        await prepare_workspace(
            binding, tmp_path / "attempt", executor=RealGitExecutor()
        )
    assert not marker.exists()


async def test_source_config_cannot_redirect_preflight_to_another_working_tree(
    source_repository, tmp_path
):
    """A registered directory cannot acquire another source's identity through core.worktree."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.development_workspace import prepare_workspace

    source, binding = source_repository
    other = tmp_path / "another-project"
    other.mkdir()
    (other / "unrelated-private-name.txt").write_text("Synthetic other-project data.")
    await fixture_git(source, "config", "core.worktree", str(other))
    with pytest.raises(RunConflict, match="registered"):
        await prepare_workspace(
            binding, tmp_path / "attempt", executor=RealGitExecutor()
        )
    assert (
        other / "unrelated-private-name.txt"
    ).read_text() == "Synthetic other-project data."


async def test_preparation_uses_explicit_namespace_paths_without_exposing_host_tree(
    source_repository, tmp_path
):
    """The Git workflow must work when execution sees mounted aliases instead of host path names."""
    from backend.runtime.development_workspace import prepare_workspace

    source, binding = source_repository
    allocation = tmp_path / "attempt"

    class NamespacedGit(RealGitExecutor):
        """Test-only mount executor; product integration still requires actual gated owner/cgroup admission."""

        def execution_path(self, path):
            """Translate only the admitted source and this one private allocation to their mount aliases."""
            path = Path(path)
            if path.is_relative_to(source):
                return Path("/run/source") / path.relative_to(source)
            if path.is_relative_to(allocation):
                return Path("/run/development") / path.relative_to(allocation)
            raise ValueError("No execution mapping for this host path")

        async def run(self, command, *, cwd, env, timeout):
            """Run actual Git in a namespace containing only source, allocation and runtime files."""
            mounts = [
                "bwrap",
                "--unshare-all",
                "--die-with-parent",
                "--cap-drop",
                "ALL",
                "--ro-bind",
                "/usr",
                "/usr",
            ]
            for name in ("bin", "lib", "lib64"):
                root = Path("/") / name
                if root.is_symlink():
                    mounts.extend(["--symlink", str(root.readlink()), str(root)])
                elif root.exists():
                    mounts.extend(["--ro-bind", str(root), str(root)])
            mounts.extend(
                [
                    "--proc",
                    "/proc",
                    "--dev",
                    "/dev",
                    "--tmpfs",
                    "/tmp",
                    "--tmpfs",
                    "/run",
                    "--dir",
                    "/home/actor",
                    "--ro-bind",
                    str(source),
                    "/run/source",
                ]
            )
            if allocation.exists():
                mounts.extend(["--bind", str(allocation), "/run/development"])
            mounts.extend(["--chdir", str(cwd), "--", *command])
            return await super().run(mounts, cwd=None, env=env, timeout=timeout)

    prepared = await prepare_workspace(binding, allocation, executor=NamespacedGit())
    assert Path(prepared.workspace) == allocation / "repository"
    assert (Path(prepared.workspace) / "value.py").read_bytes() == (
        source / "value.py"
    ).read_bytes()
    assert (
        prepared.base_sha
        == (await fixture_git(source, "rev-parse", "HEAD")).decode().strip()
    )
