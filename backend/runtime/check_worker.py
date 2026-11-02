"""Trusted stdlib check collector inside one owned namespace; untrusted child output is always data.

Reports are opened here with no-follow and finite bounds, never by following a
project-controlled path from the host. The broker still owns descendant closure.
"""

import base64
import json
import os
import selectors
import stat
import subprocess
import sys
import time


def main():
    """Run one explicit recipe with clean environment, bounded capture and a single structured terminal observation."""
    settings = json.loads(sys.argv[1])
    spec = settings["spec"]
    argv = spec["argv"]
    report = "/tmp/researcher-check.xml"
    if spec["framework"] == "pytest":
        argv = [*argv, "--junitxml=" + report]
    environment = {
        "HOME": "/home/actor",
        "TMPDIR": "/tmp",
        "PATH": "/usr/bin",
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    if settings["packages"]:
        environment["PYTHONPATH"] = "/run/researcher-check/packages"
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    complete = True
    exit_code = None
    error = None
    xml = None
    try:
        process = subprocess.Popen(
            argv,
            cwd="/run/researcher-source",
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        selector = selectors.DefaultSelector()
        deadline = time.monotonic() + spec["timeout_seconds"]
        last = time.monotonic()
        for name in streams:
            stream = getattr(process, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        try:
            while selector.get_map():
                now = time.monotonic()
                if now >= deadline:
                    complete = False
                    error = "deadline_exceeded"
                    break
                events = selector.select(min(0.05, deadline - now))
                for key, _mask in events:
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    last = time.monotonic()
                    buffer = streams[key.data]
                    remaining = spec["output_bytes"] - len(buffer)
                    buffer.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        complete = False
                        error = "output_limit"
                        break
                if error:
                    break
                if (
                    process.poll() is not None
                    and time.monotonic() - last > 0.2
                    and selector.get_map()
                ):
                    complete = False
                    error = "descendant_output_incomplete"
                    break
            if error:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=2)
            else:
                exit_code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
        finally:
            selector.close()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
        if spec["framework"] == "pytest":
            try:
                fd = os.open(report, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_size > 1024**2:
                        raise ValueError("report limit")
                    data = stream.read(1024**2 + 1)
                    if len(data) > 1024**2:
                        raise ValueError("report limit")
                    xml = base64.b64encode(data).decode("ascii")
            except (OSError, ValueError):
                pass
    except (OSError, subprocess.SubprocessError) as exc:
        complete = False
        error = type(exc).__name__
    print(
        json.dumps(
            {
                "exit_code": exit_code,
                "output_complete": complete,
                "error": error,
                "stdout": base64.b64encode(streams["stdout"]).decode("ascii"),
                "stderr": base64.b64encode(streams["stderr"]).decode("ascii"),
                "junit_xml": xml,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
