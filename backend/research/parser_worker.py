"""Fixed document worker entry point; apply Linux limits before importing the parser.

Only the host supplies bootstrap paths/budgets. Input is document bytes on stdin, not
code or a filename. This utility never receives tool credentials or model tools.
"""

import json
import resource
import sys


def main():
    """Constrain this child, decode one bounded snapshot and emit one redacted receipt."""
    options = json.loads(sys.argv[1])
    sys.path.insert(0, options["package_root"])
    from backend.research.worker_limits import apply_limits

    apply_limits(options)
    from backend.research.models import SourceTooLarge, SourceUnavailable

    try:
        data = sys.stdin.buffer.read(options["max_input_bytes"] + 1)
        if len(data) > options["max_input_bytes"]:
            raise SourceTooLarge("Document worker input exceeds its byte budget")
        if options["format"] == "pdf":
            from backend.research.pdf_text import extract_pdf

            content, provenance = extract_pdf(data)
        else:
            from backend.research.structured_text import extract_structured

            content, provenance = extract_structured(data, options["format"])
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
            "message": "Document exceeds parser memory or extraction budgets; no partial source was saved",
        }
    except SourceUnavailable as exc:
        result = {"ok": False, "code": "unavailable", "message": str(exc)}
    except Exception:  # noqa: BLE001 — redact parser internals at the process boundary
        result = {
            "ok": False,
            "code": "unavailable",
            "message": "Document worker could not extract this document reliably",
        }
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > options["max_output_bytes"]:
        encoded = b'{"ok":false,"code":"too_large","message":"Document worker output exceeds its byte budget"}'
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
