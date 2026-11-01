"""One byte-window representation for host-model and owner receipt readers."""

import base64


def output_window(chunk: bytes, *, offset: int, total_bytes: int):
    try:
        preview = chunk.decode("utf-8")
        lossy = False
    except UnicodeDecodeError:
        preview, lossy = chunk.decode("utf-8", errors="replace"), True
    return {
        "offset": offset,
        "next_offset": offset + len(chunk),
        "total_bytes": total_bytes,
        "has_more": offset + len(chunk) < total_bytes,
        "base64": base64.b64encode(chunk).decode("ascii"),
        "text": preview,
        "utf8_lossy": lossy,
    }
