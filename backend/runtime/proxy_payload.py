"""Trusted post-G private-NET relay; no imports from source or provider secrets."""

import array
import ctypes
import os
import select
import signal
import socket
import sys
import time


def install_native_filter():
    """Apply the mounted native seccomp program after enabling no_new_privs, refusing filter setup failure."""
    with open("/run/researcher-host/native-filter", "rb") as source:
        data = source.read()

    class Program(ctypes.Structure):
        """Match Linux sock_fprog memory layout for the trusted native filter bytecode."""
        _fields_ = [("length", ctypes.c_ushort), ("filter", ctypes.c_void_p)]

    instructions = ctypes.create_string_buffer(data)
    program = Program(len(data) // 8, ctypes.addressof(instructions))
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) or libc.prctl(22, 2, ctypes.byref(program), 0, 0):
        raise RuntimeError("Native client filter unavailable")


def stop_child(pid):
    """Terminate and reap this direct child, escalating from SIGTERM to SIGKILL after one second."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        if os.waitpid(pid, os.WNOHANG)[0]:
            return
        time.sleep(0.01)
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)


def main():
    """Relay accepted private-loopback sockets to the host via SCM_RIGHTS and retire the filtered native child on bridge loss."""
    bridge_fd = int(sys.argv[1])
    for item in os.listdir("/proc/self/fd"):
        fd = int(item)
        if fd not in (0, 1, 2, bridge_fd):
            try:
                os.close(fd)
            except OSError:
                pass
    # The native child must not inspect or duplicate the relay's private FDs.
    if ctypes.CDLL(None).prctl(4, 0, 0, 0, 0):
        raise RuntimeError("Private relay protection unavailable")
    bridge = socket.socket(fileno=bridge_fd)
    bridge.settimeout(0.2)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    listener.setblocking(False)
    proxy = "http://127.0.0.1:" + str(listener.getsockname()[1])
    child = os.fork()
    if child == 0:
        bridge.close()
        listener.close()
        try:
            install_native_filter()
            env = {
                **os.environ,
                "HTTP_PROXY": proxy,
                "HTTPS_PROXY": proxy,
                "ALL_PROXY": proxy,
                "NO_PROXY": "",
            }
            os.execvpe(sys.argv[2], sys.argv[2:], env)
        except Exception:  # noqa: BLE001 — no dependency details on the protocol pipe
            os._exit(126)
    reaped = False
    status = 125
    try:
        while True:
            done, result = os.waitpid(child, os.WNOHANG)
            if done:
                reaped = True
                status = os.waitstatus_to_exitcode(result)
                if status < 0:
                    status = 128 - status
                break
            ready, _, _ = select.select([listener, bridge], [], [], 0.05)
            if bridge in ready:
                break  # Host EOF/unexpected control retires this relay.
            if listener in ready:
                try:
                    accepted, _ = listener.accept()
                except BlockingIOError:
                    continue
                with accepted:
                    bridge.sendmsg(
                        [b"F"],
                        [
                            (
                                socket.SOL_SOCKET,
                                socket.SCM_RIGHTS,
                                array.array("i", [accepted.fileno()]),
                            )
                        ],
                    )
    finally:
        listener.close()
        bridge.close()
        if not reaped:
            stop_child(child)
    return status


if __name__ == "__main__":
    try:
        result = main()
    except Exception:  # noqa: BLE001 — fixed error, no raw source/proxy diagnostics
        result = 125
    sys.exit(result)
