"""Published Ken in a per-workspace OS boundary, never in an inference peer."""

import hashlib
import json
import os
import shutil
import stat
import subprocess
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from backend.runtime.ken_grammars import VERSION as GRAMMAR_VERSION
from backend.runtime.ken_grammars import cache_directory, verify_grammars

KEN_VERSION = "0.18.0"


@dataclass(frozen=True)
class KenInstallation:
    """A verified published tool installation whose parser resources share its trusted boundary."""

    executable: Path
    tool_root: Path
    python_root: Path
    assets: tuple[dict, ...] = ()
    grammar_fingerprint: str | None = None

    @classmethod
    def inspect(cls, executable: Path, *, require_grammars=True):
        """Verify the trusted published tool and offline grammars; only explicit preparation may omit the cache check."""
        executable = executable.resolve(strict=True)
        tool = executable.parent.parent
        python = tool / "bin/python"
        if not python.is_file() or not os.access(executable, os.X_OK):
            raise ValueError("Ken requires a trusted isolated Python tool installation")
        script = """
import importlib.metadata as m, json, sys
from pathlib import Path
import ken
d=m.distribution("ken-rank")
folder=Path(ken.__file__).parent/"embedder/data"
models=[]
for name in ("potion-code-16M-v2.json","code-context-int8.json","ettin-68m-fp32.json","es-en-ct2-int8.json"):
    manifest=folder/name
    if manifest.is_file():
        from ken.model_assets import ModelAssets
        value=json.loads(manifest.read_text())
        models.append(ModelAssets.from_dict(value.get("source",value)).to_dict())
print(json.dumps({"version":d.version,"grammar_version":m.version("tree-sitter-language-pack"),"prefix":sys.prefix,"base_prefix":sys.base_prefix,"package":str(Path(ken.__file__).resolve()),"direct_url":d.read_text("direct_url.json"),"models":models}))
"""
        try:
            result = subprocess.run(
                [str(python), "-I", "-c", script],
                cwd="/",
                env={"PATH": os.defpath, "LANG": "C.UTF-8"},
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            info = json.loads(result.stdout)
            direct = json.loads(info["direct_url"] or "{}")
            if (
                info["version"] != KEN_VERSION
                or info["grammar_version"] != GRAMMAR_VERSION
                or Path(info["prefix"]).resolve() != tool
                or not Path(info["package"]).is_relative_to(tool)
                or direct.get("dir_info", {}).get("editable")
            ):
                raise ValueError(
                    "Ken must be the isolated published ken-rank==0.18.0 installation"
                )
            base = Path(info["base_prefix"]).resolve(strict=True)
            cfg = dict(
                line.split(" = ", 1)
                for line in (tool / "pyvenv.cfg").read_text().splitlines()
                if " = " in line
            )
            # Preserve the interpreter's installation alias: venv executable
            # symlinks can point through it even when sys.base_prefix is canonical.
            alias = Path(cfg["home"]).parent
            if not alias.is_absolute() or alias.resolve(strict=True) != base:
                raise ValueError("Unexpected Ken interpreter installation")
            if base in {Path("/"), Path.home()} or tool in {Path("/"), Path.home()}:
                raise ValueError("Ken tool roots must not expose host root or home")
            grammar = verify_grammars(tool) if require_grammars else None
            return cls(executable, tool, alias, tuple(info["models"]), grammar["fingerprint"] if grammar else None)
        except (subprocess.SubprocessError, json.JSONDecodeError, KeyError) as exc:
            raise ValueError("Could not verify isolated ken-rank==0.18.0") from exc


@dataclass(frozen=True)
class WorkerLaunch:
    command: tuple[str, ...]
    env: dict[str, str]
    pass_fds: tuple[int, ...]


@contextmanager
def worker_process(
    installation: KenInstallation,
    *,
    workspace: Path,
    mode: str = "mcp",
    model_cache: Path | None = None,
    expected_identity: tuple[int, int] | None = None,
    stable_view: bool = False,
    payload_prefix: tuple[str, ...] = (),
):
    """Pin source/state directories before mounting; only .ken is writable.

    Input environment is intentionally ignored, including HOME, proxy/provider
    settings and grant credentials. The returned FDs must remain owned until
    child creation, then be closed by this context. Never reuse another run's
    launch or descriptors. This requires Linux bubblewrap with bind-fd support.
    """
    if mode not in {"mcp", "prepare"}:
        raise ValueError("Unknown Ken worker operation")
    if expected_identity is not None and (
        not isinstance(expected_identity, tuple)
        or len(expected_identity) != 2
        or any(type(value) is not int for value in expected_identity)
        or expected_identity[0] < 0
        or expected_identity[1] <= 0
    ):
        raise ValueError("Expected a valid workspace device/inode identity")
    root = workspace.resolve(strict=True)
    from backend.runtime.workspaces import PEER_WORKSPACE

    if type(stable_view) is not bool or not isinstance(payload_prefix, tuple):
        raise ValueError("Host-selected worker launch options required")
    view = PEER_WORKSPACE if stable_view else root
    for tool in (installation.tool_root, installation.python_root):
        if tool.is_relative_to(root):
            raise ValueError("Workspace cannot contain the trusted tool installation")
    grammar = verify_grammars(installation.tool_root)
    if grammar["fingerprint"] != installation.grammar_fingerprint:
        raise ValueError("Ken grammar preparation changed after installation inspection")
    bubblewrap = shutil.which("bwrap")
    if not bubblewrap:
        raise ValueError("Isolated Ken requires bubblewrap; no unsandboxed fallback")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    if model_cache is not None and model_cache.resolve().is_relative_to(root):
        raise ValueError("Trusted model cache must be outside the workspace")
    root_fd = os.open(root, directory_flags)
    state_fd = None
    asset_handles = ExitStack()
    try:
        opened = os.fstat(root_fd)
        if (
            expected_identity is not None
            and (opened.st_dev, opened.st_ino) != expected_identity
        ):
            raise ValueError("Workspace identity changed before opening Ken source")
        try:
            os.mkdir(".ken", mode=0o700, dir_fd=root_fd)
        except FileExistsError:
            pass
        try:
            state_fd = os.open(".ken", directory_flags, dir_fd=root_fd)
        except OSError as exc:
            raise ValueError(
                "Ken state directory must not be a symlink or foreign mount"
            ) from exc
        if not stat.S_ISDIR(os.fstat(state_fd).st_mode):
            raise ValueError("Ken state must be a directory")
        command = [
            bubblewrap,
            "--unshare-all",
            "--new-session",
            "--die-with-parent",
            "--cap-drop",
            "ALL",
            "--clearenv",
        ]
        for path in ("/usr", "/bin", "/lib", "/lib64"):
            if Path(path).exists():
                command += ["--ro-bind", path, path]
        command += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
        for path in {installation.tool_root, installation.python_root}:
            if not path.is_relative_to(Path("/usr")):
                command += ["--ro-bind", str(path), str(path)]
        asset_fds = []
        if model_cache is not None:
            for model in installation.assets:
                revision = model["revision"]
                repository = "models--" + model["model_id"].replace("/", "--")
                snapshot = model_cache / repository / "snapshots" / revision
                for name, expected in model["artifacts"].items():
                    try:
                        handle = asset_handles.enter_context(
                            (snapshot / name).open("rb")
                        )
                    except OSError as exc:
                        raise ValueError(
                            f"Prepare pinned public Ken model {model['model_id']}@{revision} before starting"
                        ) from exc
                    if (
                        not stat.S_ISREG(os.fstat(handle.fileno()).st_mode)
                        or os.fstat(handle.fileno()).st_size != expected["bytes"]
                        or hashlib.file_digest(handle, "sha256").hexdigest()
                        != expected["sha256"]
                    ):
                        raise ValueError(
                            "Pinned Ken model artifact is missing or changed"
                        )
                    destination = (
                        Path("/opt/researcher-ken-models/hub")
                        / repository
                        / "snapshots"
                        / revision
                        / name
                    )
                    command += ["--ro-bind-fd", str(handle.fileno()), str(destination)]
                    asset_fds.append(handle.fileno())
        command += [
            "--dir",
            "/tmp/home",
            "--dir",
            "/tmp/cache",
            "--ro-bind-fd",
            str(root_fd),
            str(view),
            "--bind-fd",
            str(state_fd),
            str(view / ".ken"),
            "--setenv",
            "PATH",
            os.defpath,
            "--setenv",
            "HOME",
            "/tmp/home",
            "--setenv",
            "XDG_CACHE_HOME",
            str(cache_directory(installation.tool_root)),
            "--setenv",
            "LANG",
            "C.UTF-8",
            "--setenv",
            "PYTHONNOUSERSITE",
            "1",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--setenv",
            "HF_HUB_CACHE",
            "/opt/researcher-ken-models/hub",
            "--setenv",
            "HF_HUB_OFFLINE",
            "1",
            "--setenv",
            "TRANSFORMERS_OFFLINE",
            "1",
            "--setenv",
            "HF_HUB_DISABLE_TELEMETRY",
            "1",
            "--setenv",
            "OMP_NUM_THREADS",
            "1",
            "--setenv",
            "OPENBLAS_NUM_THREADS",
            "1",
            "--setenv",
            "TOKENIZERS_PARALLELISM",
            "false",
            "--setenv",
            "KEN_PROJECT_ROOT",
            str(view),
            "--chdir",
            "/tmp",
            *payload_prefix,
            str(installation.executable),
        ]
        command += (
            ["mcp", str(view)]
            if mode == "mcp"
            else ["retrieval", "prepare", "--path", str(view), "--json"]
        )
        yield WorkerLaunch(
            tuple(command),
            {"PATH": os.defpath, "LANG": "C.UTF-8"},
            (root_fd, state_fd, *asset_fds),
        )
    finally:
        asset_handles.close()
        if state_fd is not None:
            os.close(state_fd)
        os.close(root_fd)


def main():
    """MCP child entry point; open descriptors here, never pass them via prompts."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ken-command", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--model-cache", type=Path, required=True)
    parser.add_argument("--expected-device", type=int)
    parser.add_argument("--expected-inode", type=int)
    args = parser.parse_args()
    if (args.expected_device is None) != (args.expected_inode is None):
        parser.error("Expected device and inode must be provided together")
    expected_identity = (
        (args.expected_device, args.expected_inode)
        if args.expected_device is not None
        else None
    )
    installation = KenInstallation.inspect(args.ken_command)
    with worker_process(
        installation,
        workspace=args.workspace,
        mode="prepare" if args.prepare else "mcp",
        model_cache=args.model_cache,
        expected_identity=expected_identity,
    ) as launch:
        for descriptor in launch.pass_fds:
            os.set_inheritable(descriptor, True)
        os.execve(launch.command[0], launch.command, launch.env)


if __name__ == "__main__":
    main()
