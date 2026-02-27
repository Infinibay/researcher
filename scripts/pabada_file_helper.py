#!/usr/bin/env python3
"""pabada-file-helper — file operations inside agent pods.

Reads a JSON request from stdin, performs the operation, and writes
a JSON response to stdout.  This avoids shell-escaping issues when
passing file content as command arguments.

Operations: read, write, edit, list, search, glob

Usage:
    echo '{"op":"read","path":"main.py"}' | pabada-file-helper
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_DIR_LISTING = 1000
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox", ".mypy_cache"}


def ok(data):
    json.dump({"ok": True, "data": data}, sys.stdout)
    sys.stdout.write("\n")


def err(message):
    json.dump({"ok": False, "error": message}, sys.stdout)
    sys.stdout.write("\n")


def op_read(req):
    path = req["path"]
    offset = req.get("offset")
    limit = req.get("limit")

    if not os.path.exists(path):
        return err(f"File not found: {path}")
    if not os.path.isfile(path):
        return err(f"Not a file: {path}")
    if os.path.getsize(path) > MAX_FILE_SIZE:
        return err(f"File too large: {os.path.getsize(path)} bytes")

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except PermissionError:
        return err(f"Permission denied: {path}")
    except Exception as e:
        return err(f"Error reading: {e}")

    total = len(lines)
    if offset is not None or limit is not None:
        start = max((offset or 1) - 1, 0)
        end = start + limit if limit is not None else total
        selected = lines[start:end]
        numbered = [f"{i:>6}\t{l.rstrip()}" for i, l in enumerate(selected, start=start + 1)]
    else:
        numbered = [f"{i:>6}\t{l.rstrip()}" for i, l in enumerate(lines, start=1)]

    ok({"content": "\n".join(numbered), "total_lines": total})


def op_write(req):
    path = req["path"]
    content = req["content"]
    mode = req.get("mode", "w")

    content_bytes = content.encode("utf-8")
    if len(content_bytes) > MAX_FILE_SIZE:
        return err(f"Content too large: {len(content_bytes)} bytes")

    before_hash = None
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                before_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        except Exception:
            pass

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    try:
        if mode == "w":
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".pabada_")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp, path)
            except Exception:
                os.unlink(tmp)
                raise
        else:
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
    except PermissionError:
        return err(f"Permission denied: {path}")
    except Exception as e:
        return err(f"Error writing: {e}")

    after_hash = hashlib.sha256(content_bytes).hexdigest()[:16]
    action = "modified" if before_hash else "created"

    ok({"path": path, "action": action, "size_bytes": len(content_bytes),
         "before_hash": before_hash, "after_hash": after_hash})


def op_edit(req):
    path = req["path"]
    old_string = req["old_string"]
    new_string = req["new_string"]
    replace_all = req.get("replace_all", False)

    if old_string == new_string:
        return err("old_string and new_string are identical")

    if not os.path.exists(path):
        return err(f"File not found: {path}")
    if not os.path.isfile(path):
        return err(f"Not a file: {path}")

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except PermissionError:
        return err(f"Permission denied: {path}")
    except Exception as e:
        return err(f"Error reading: {e}")

    count = content.count(old_string)
    if count == 0:
        return err(f"old_string not found in {path}")
    if count > 1 and not replace_all:
        return err(f"old_string appears {count} times; use replace_all or add context")

    before_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    if replace_all:
        new_content = content.replace(old_string, new_string)
        replacements = count
    else:
        new_content = content.replace(old_string, new_string, 1)
        replacements = 1

    new_bytes = new_content.encode("utf-8")
    if len(new_bytes) > MAX_FILE_SIZE:
        return err(f"Resulting file too large: {len(new_bytes)} bytes")

    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".pabada_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_content)
            os.replace(tmp, path)
        except Exception:
            os.unlink(tmp)
            raise
    except PermissionError:
        return err(f"Permission denied: {path}")
    except Exception as e:
        return err(f"Error writing: {e}")

    after_hash = hashlib.sha256(new_bytes).hexdigest()[:16]

    ok({"path": path, "action": "modified", "replacements": replacements,
         "size_bytes": len(new_bytes), "before_hash": before_hash, "after_hash": after_hash})


def op_list(req):
    path = req.get("path", ".")
    recursive = req.get("recursive", False)
    pattern = req.get("pattern")

    if not os.path.isdir(path):
        return err(f"Directory not found: {path}")

    entries = []
    count = 0

    if recursive:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for name in files:
                if name.startswith("."):
                    continue
                fp = os.path.join(root, name)
                rel = os.path.relpath(fp, path)
                if pattern and not _match_glob(rel, pattern):
                    continue
                try:
                    st = os.stat(fp)
                    entries.append({"path": rel, "size": st.st_size, "type": "file"})
                except OSError:
                    entries.append({"path": rel, "type": "file"})
                count += 1
                if count >= MAX_DIR_LISTING:
                    break
            if count >= MAX_DIR_LISTING:
                break
    else:
        try:
            for name in sorted(os.listdir(path)):
                if name.startswith("."):
                    continue
                fp = os.path.join(path, name)
                try:
                    st = os.stat(fp)
                    ftype = "dir" if os.path.isdir(fp) else "file"
                    entries.append({"path": name, "size": st.st_size, "type": ftype})
                except OSError:
                    entries.append({"path": name})
                count += 1
                if count >= MAX_DIR_LISTING:
                    break
        except PermissionError:
            return err(f"Permission denied: {path}")

    ok({"path": path, "entries": entries, "count": len(entries),
         "truncated": count >= MAX_DIR_LISTING})


def op_search(req):
    pattern = req["pattern"]
    path = req.get("path", ".")
    case_sensitive = req.get("case_sensitive", True)
    max_results = req.get("max_results", 50)
    file_extensions = req.get("file_extensions")
    context_lines = req.get("context_lines", 0)

    cmd = ["grep", "-rn", "-E"]
    if not case_sensitive:
        cmd.append("-i")
    if context_lines > 0:
        cmd.extend(["-C", str(context_lines)])
    if file_extensions:
        for ext in file_extensions:
            ext = ext if ext.startswith(".") else f".{ext}"
            cmd.extend(["--include", f"*{ext}"])
    for d in SKIP_DIRS:
        cmd.extend(["--exclude-dir", d])
    cmd.extend(["--", pattern, path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return err("Search timed out")
    except FileNotFoundError:
        return err("grep not available")

    if result.returncode == 1:
        return ok({"pattern": pattern, "match_count": 0, "matches": []})
    if result.returncode not in (0, 1):
        return err(f"Search failed: {result.stderr.strip()}")

    lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    matches = []
    for line in lines:
        if line == "--":
            continue
        sep1 = line.find(":")
        if sep1 == -1:
            continue
        file_part = line[:sep1]
        rest = line[sep1 + 1:]
        sep2 = rest.find(":")
        if sep2 == -1:
            sep2 = rest.find("-")
            if sep2 == -1:
                continue
        try:
            line_num = int(rest[:sep2])
        except ValueError:
            continue
        matches.append({"file": file_part, "line": line_num, "content": rest[sep2 + 1:]})
        if len(matches) >= max_results:
            break

    ok({"pattern": pattern, "match_count": len(matches), "matches": matches})


def op_glob(req):
    pattern = req["pattern"]
    path = req.get("path", ".")
    content_pattern = req.get("content_pattern")
    case_sensitive = req.get("case_sensitive", True)
    max_results = req.get("max_results", 100)

    if not os.path.isdir(path):
        return err(f"Directory not found: {path}")

    content_re = None
    if content_pattern:
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            content_re = re.compile(content_pattern, flags)
        except re.error as e:
            return err(f"Invalid regex: {e}")

    base = Path(path)
    matches = []
    for fp in base.glob(pattern):
        if fp.is_dir():
            continue
        parts = fp.relative_to(base).parts
        if any(p in SKIP_DIRS or p.startswith(".") for p in parts[:-1]):
            continue
        if fp.name.startswith("."):
            continue
        if content_re:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                if not content_re.search(text):
                    continue
            except (PermissionError, OSError):
                continue
        rel = str(fp.relative_to(base))
        try:
            st = fp.stat()
            matches.append({"path": rel, "size": st.st_size})
        except OSError:
            matches.append({"path": rel})
        if len(matches) >= max_results:
            break

    ok({"pattern": pattern, "match_count": len(matches), "matches": matches,
         "truncated": len(matches) >= max_results})


def _match_glob(path, pattern):
    """Simple glob match for filtering."""
    from fnmatch import fnmatch
    return fnmatch(path, pattern)


OPERATIONS = {
    "read": op_read,
    "write": op_write,
    "edit": op_edit,
    "list": op_list,
    "search": op_search,
    "glob": op_glob,
}


def main():
    try:
        raw = sys.stdin.read()
        req = json.loads(raw)
    except json.JSONDecodeError as e:
        err(f"Invalid JSON input: {e}")
        sys.exit(1)

    op = req.get("op")
    if op not in OPERATIONS:
        err(f"Unknown operation: {op}. Valid: {list(OPERATIONS.keys())}")
        sys.exit(1)

    OPERATIONS[op](req)


if __name__ == "__main__":
    main()
