"""Protect actual model-cache lock consumers when replacing vulnerable transitive dependencies."""

import os
import stat
import subprocess
import sys

from huggingface_hub.utils import WeakFileLock


def test_cache_lock_preserves_an_existing_nonlock_file(tmp_path):
    """A pre-existing file at the cache-lock name must retain its bytes and private permissions."""
    path = tmp_path / 'download.lock'
    path.write_bytes(b'existing owner data, not a lock marker')
    path.chmod(0o600)
    with WeakFileLock(path, timeout=1):
        assert path.read_bytes() == b'existing owner data, not a lock marker'
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert path.read_bytes() == b'existing owner data, not a lock marker'


def test_cache_lock_excludes_another_process_and_releases_afterwards(tmp_path):
    """The unchanged Hugging Face wrapper still enforces cross-process exclusion and later acquisition."""
    path = tmp_path / 'download.lock'
    child = '''from huggingface_hub.utils import WeakFileLock
from filelock import Timeout
import sys
try:
    with WeakFileLock(sys.argv[1], timeout=0.1):
        raise SystemExit(3)
except Timeout:
    print("blocked")
'''
    with WeakFileLock(path, timeout=1):
        result = subprocess.run(
            [sys.executable, '-c', child, str(path)], cwd=tmp_path,
            env={'PATH': os.defpath}, capture_output=True, text=True,
            timeout=5, check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == 'blocked'
    with WeakFileLock(path, timeout=1):
        assert path.exists()
