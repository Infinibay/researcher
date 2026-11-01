"""Fixed PDF worker entry point; apply Linux limits before importing the parser.

Only the host supplies bootstrap paths/budgets. Input is PDF bytes on stdin, not
code or a filename. This utility never receives tool credentials or model tools.
"""

import ctypes
import json
import math
import os
import resource
import signal
import sys


def main():
    """Constrain this child, decode one bounded snapshot and emit one redacted receipt."""
    options = json.loads(sys.argv[1])
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != options["parent"]:
        raise SystemExit(125)
    resource.setrlimit(
        resource.RLIMIT_CPU, (options["cpu_seconds"], options["cpu_seconds"] + 1)
    )
    resource.setrlimit(
        resource.RLIMIT_AS, (options["memory_bytes"], options["memory_bytes"])
    )
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    signal.alarm(math.ceil(options["wall_seconds"]) + 1)
    sys.path[:0] = [options["package_root"], options["dependencies"]]
    from backend.research.models import SourceTooLarge, SourceUnavailable

    try:
        from backend.research.pdf_text import extract_pdf

        data = sys.stdin.buffer.read(options["max_input_bytes"] + 1)
        if len(data) > options["max_input_bytes"]:
            raise SourceTooLarge("PDF worker input exceeds its byte budget")
        content, provenance = extract_pdf(data)
        provenance["execution"] = {
            "cpu_limit_seconds": resource.getrlimit(resource.RLIMIT_CPU)[0],
            "cpu_hard_limit_seconds": resource.getrlimit(resource.RLIMIT_CPU)[1],
            "address_space_limit_bytes": resource.getrlimit(resource.RLIMIT_AS)[1],
        }
        result = {"ok": True, "content": content, "provenance": provenance}
    except (MemoryError, SourceTooLarge):
        result = {
            "ok": False,
            "code": "too_large",
            "message": "PDF exceeds parser memory or extraction budgets; no partial source was saved",
        }
    except SourceUnavailable as exc:
        result = {"ok": False, "code": "unavailable", "message": str(exc)}
    except Exception:  # noqa: BLE001 — redact parser internals at the process boundary
        result = {
            "ok": False,
            "code": "unavailable",
            "message": "PDF worker could not extract this document reliably",
        }
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > options["max_output_bytes"]:
        encoded = b'{"ok":false,"code":"too_large","message":"PDF worker output exceeds its byte budget"}'
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
