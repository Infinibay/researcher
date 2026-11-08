"""Prepare public Ken grammars explicitly and verify their trusted tool-installation cache offline.

The cache manifest shares the executable's trusted installation boundary. Serving
never downloads grammars or trusts a manifest supplied by a managed source tree.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path

VERSION = "1.22.1"
ARCHIVE_BYTES = 23031807
ARCHIVE_SHA256 = "4ad211e4a265be2106909ef9db4ccdc706e557436a446fbc10afbf23d668a2a5"
ARCHIVE_URL = f"https://github.com/xberg-io/tree-sitter-language-pack/releases/download/v{VERSION}/parsers-linux-x86_64.tar.zst"
MAX_BYTES = 768 * 1024**2
MAX_FILES = 512
NAME = re.compile(r"libtree_sitter_[A-Za-z0-9_]+\.so\Z")


def cache_directory(tool_root):
    """Locate public parser resources inside the already trusted, read-only tool installation."""
    return Path(tool_root) / "share/researcher-ken-cache"


def verify_grammars(tool_root):
    """Verify bounded regular files against the installation manifest without importing a loader or accessing a network."""
    return _verify_cache(cache_directory(tool_root))


def _verify_cache(cache):
    """Validate the complete declared cache before exposing it as a prepared installation."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        root = os.open(cache, flags | os.O_DIRECTORY)
        try:
            manifest_fd = os.open("manifest.json", flags | os.O_NONBLOCK, dir_fd=root)
            with os.fdopen(manifest_fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 128000:
                    raise ValueError("Invalid Ken grammar manifest")
                manifest = json.loads(stream.read(128001))
            if (not isinstance(manifest, dict) or manifest.get("format") != 1
                    or manifest.get("version") != VERSION
                    or manifest.get("archive_sha256") != ARCHIVE_SHA256):
                raise ValueError("Ken grammar manifest does not describe the pinned release")
            files = manifest.get("files")
            if (not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES
                    or "libtree_sitter_python.so" not in files):
                raise ValueError("Ken grammar manifest must include Python and bounded resources")
            libs = os.open(f"tree-sitter-language-pack/v{VERSION}/libs", flags | os.O_DIRECTORY, dir_fd=root)
            try:
                total = 0
                for name, expected in files.items():
                    if (not NAME.fullmatch(name) or not isinstance(expected, dict)
                            or type(expected.get("bytes")) is not int
                            or not 0 < expected["bytes"] <= MAX_BYTES
                            or not isinstance(expected.get("sha256"), str)
                            or not re.fullmatch(r"[a-f0-9]{64}", expected["sha256"])):
                        raise ValueError("Invalid Ken grammar resource declaration")
                    total += expected["bytes"]
                    if total > MAX_BYTES:
                        raise ValueError("Ken grammar resources exceed preparation budget")
                    fd = os.open(name, flags | os.O_NONBLOCK, dir_fd=libs)
                    with os.fdopen(fd, "rb") as stream:
                        entry = os.fstat(stream.fileno())
                        if (not stat.S_ISREG(entry.st_mode) or entry.st_size != expected["bytes"]
                                or hashlib.file_digest(stream, "sha256").hexdigest() != expected["sha256"]):
                            raise ValueError("Ken grammar resource is missing or changed")
            finally:
                os.close(libs)
        finally:
            os.close(root)
    except (OSError, json.JSONDecodeError, TypeError, KeyError) as error:
        raise ValueError("Prepare the pinned Ken grammars before starting work; no download was attempted") from error
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"cache": str(cache), "version": VERSION, "files": len(files), "bytes": total, "fingerprint": fingerprint}


def prepare_grammars(tool_root, archive):
    """Unpack one exact public Linux x86_64 archive into a new trusted cache, preserving every existing invalid path."""
    target = cache_directory(tool_root)
    if target.exists() or target.is_symlink():
        return verify_grammars(tool_root)
    archive = Path(archive).resolve(strict=True)
    with archive.open("rb") as stream:
        if (not stat.S_ISREG(os.fstat(stream.fileno()).st_mode)
                or os.fstat(stream.fileno()).st_size != ARCHIVE_BYTES
                or hashlib.file_digest(stream, "sha256").hexdigest() != ARCHIVE_SHA256):
            raise ValueError("Ken grammar archive differs from the pinned release")
        stream.seek(0)
        target.parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ken-grammars-", dir=target.parent) as temporary:
            stage = Path(temporary)
            libs = stage / f"tree-sitter-language-pack/v{VERSION}/libs"
            libs.mkdir(parents=True)
            process = subprocess.Popen(["zstd", "-dc"], stdin=stream, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            files, total = {}, 0
            try:
                with tarfile.open(fileobj=process.stdout, mode="r|") as package:
                    for entry in package:
                        if entry.isdir() and entry.name in (".", "./"):
                            continue
                        name = entry.name.removeprefix("./")
                        if (not entry.isfile() or not NAME.fullmatch(name) or name in files
                                or len(files) >= MAX_FILES or entry.size <= 0):
                            raise ValueError("Unexpected entry in pinned Ken grammar archive")
                        total += entry.size
                        if total > MAX_BYTES:
                            raise ValueError("Ken grammar archive exceeds preparation budget")
                        with package.extractfile(entry) as incoming, (libs / name).open("xb") as outgoing:
                            shutil.copyfileobj(incoming, outgoing, length=131072)
                            outgoing.flush()
                            os.fsync(outgoing.fileno())
                        path = libs / name
                        with path.open("rb") as content:
                            files[name] = {"bytes": entry.size, "sha256": hashlib.file_digest(content, "sha256").hexdigest()}
                        path.chmod(0o444)
                if process.wait(timeout=15) != 0:
                    raise ValueError("Could not decompress pinned Ken grammar archive")
            finally:
                process.stdout.close()
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=15)
            (stage / "manifest.json").write_text(json.dumps({"format": 1, "version": VERSION,
                "archive_sha256": ARCHIVE_SHA256, "files": files}, sort_keys=True) + "\n")
            _verify_cache(stage)
            # Reserve without replacing a raced or unknown existing directory.
            target.mkdir(mode=0o755)
            for entry in stage.iterdir():
                entry.rename(target / entry.name)
    return verify_grammars(tool_root)
