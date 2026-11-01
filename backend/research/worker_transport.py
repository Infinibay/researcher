"""Bounded IPC and pidfd lifetime for fixed trusted document workers, never model programs.

Callers supply only host-fixed entry points and explicitly pinned public asset FDs.
The operation owner stays registered until this child is physically reaped.
"""

import json
import os
import selectors
import signal
import subprocess
import sys
import time

from backend.research.models import ResearchForbidden, SourceTooLarge, SourceUnavailable
from backend.runtime.peer_process import _pidfd, _signal


def exchange(data, *, worker, options, limits, cancelled, label="PDF", pass_fds=()):
    """Exchange one bounded payload and reap before returning, even after cancellation/failure."""
    wall_seconds = options["wall_seconds"]
    deadline = time.monotonic() + wall_seconds
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", "-S", str(worker), json.dumps(options)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd="/",
            env={
                "LANG": "C.UTF-8",
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "TOKENIZERS_PARALLELISM": "false",
            },
            close_fds=True,
            pass_fds=pass_fds,
            bufsize=0,
        )
    except OSError as exc:
        raise SourceUnavailable(f"{label} worker could not be started") from exc
    pidfd = None
    output = bytearray()
    try:
        pidfd = _pidfd(process.pid)
        with selectors.DefaultSelector() as selector:
            for stream, event in (
                (process.stdin, selectors.EVENT_WRITE),
                (process.stdout, selectors.EVENT_READ),
            ):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, event)
            sent, eof = 0, False
            while True:
                if cancelled.is_set():
                    raise ResearchForbidden(
                        f"{label} operation authority was withdrawn during extraction"
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SourceTooLarge(
                        f"{label} parser exceeded its wall-clock budget; no partial source was saved"
                    )
                for key, _ in selector.select(min(0.05, remaining)):
                    stream = key.fileobj
                    if stream is process.stdin:
                        try:
                            sent += os.write(stream.fileno(), data[sent : sent + 65536])
                        except BrokenPipeError:
                            sent = len(data)
                        if sent == len(data):
                            selector.unregister(stream)
                            stream.close()
                    else:
                        chunk = os.read(stream.fileno(), 65536)
                        if chunk:
                            if len(output) + len(chunk) > limits.max_output_bytes:
                                raise SourceTooLarge(
                                    f"{label} worker exceeded its output byte budget"
                                )
                            output.extend(chunk)
                        else:
                            selector.unregister(stream)
                            stream.close()
                            eof = True
                if process.poll() is not None and eof:
                    break
        if process.returncode in (-signal.SIGXCPU, -signal.SIGALRM):
            raise SourceTooLarge(f"{label} parser exceeded its OS execution budget")
        if process.returncode != 0:
            raise SourceUnavailable(
                f"{label} worker terminated without a valid result; no partial source was saved"
            )
        return bytes(output)
    except (ResearchForbidden, SourceTooLarge):
        raise
    except OSError as exc:
        raise SourceUnavailable(
            f"{label} worker could not start or exchange its bounded snapshot"
        ) from exc
    finally:
        # Do not finish the registered operation until the original child is
        # actually reaped. A stalled kernel wait remains pending, never closed.
        try:
            if process.poll() is None and pidfd is not None:
                _signal(pidfd)
        finally:
            # If pidfd admission failed, no input was released. EOF plus
            # the worker's own CPU/alarm fuse ends that trusted bootstrap.
            process.stdin.close()
            process.wait()
        for stream in (process.stdin, process.stdout):
            stream.close()
        if pidfd is not None:
            os.close(pidfd)
