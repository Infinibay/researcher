"""Owned descriptor channel for a future private-network native helper.

Only an inherited Unix endpoint can supply accepted streams; there is no host TCP
proxy listener or model-selected host IPC address. The caller must close its
child-end copy after spawn, and keep a duplicated FD pinned until that spawn.
"""

import array
import os
import socket
import threading
import time


class EgressChannel:
    def __init__(self, proxy):
        self.proxy = proxy
        self._lock = threading.Lock()
        self._parent, self._child = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_SEQPACKET
        )
        self._reader = threading.Thread(
            target=self._receive, name="researcher-egress-fds", daemon=True
        )
        self._reader.start()

    def duplicate_child(self):
        """Caller owns a stable FD through spawn; withdrawal cannot reuse it."""
        with self._lock:
            if self._child is None:
                raise RuntimeError("Private egress endpoint closed")
            return os.dup(self._child.fileno())

    def close_child_end(self):
        with self._lock:
            child, self._child = self._child, None
        if child is not None:
            child.close()

    def withdraw(self):
        self.proxy.withdraw()
        self.close_child_end()
        try:
            self._parent.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._parent.close()

    def close(self, *, timeout=4):
        deadline = time.monotonic() + timeout
        self.withdraw()
        self._reader.join(timeout=min(timeout, 1))
        self.proxy.close(timeout=max(0, deadline - time.monotonic()))
        if self._reader.is_alive():
            raise RuntimeError("Egress descriptor reader has not closed")

    def _receive(self):
        received = 0
        try:
            while True:
                descriptors = []
                try:
                    data, ancillary, flags, _ = self._parent.recvmsg(
                        1,
                        socket.CMSG_SPACE(8 * array.array("i").itemsize),
                        socket.MSG_CMSG_CLOEXEC,
                    )
                    invalid = bool(flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC))
                    for level, kind, value in ancillary:
                        if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
                            invalid = True
                            continue
                        chunk = array.array("i")
                        chunk.frombytes(
                            value[: len(value) - len(value) % chunk.itemsize]
                        )
                        descriptors.extend(chunk)
                    if not data:
                        break
                    if invalid or data != b"F" or len(descriptors) != 1:
                        raise ValueError("Invalid private egress frame")
                    received += 1
                    if received > self.proxy.policy.max_connections:
                        raise ValueError("Private egress delivery budget exhausted")
                    raw = socket.socket(fileno=descriptors[0])
                    descriptors.clear()
                    try:
                        self.proxy.submit(raw)
                    except RuntimeError:
                        # Full live capacity rejects this stream. The total
                        # descriptor budget also bounds repeated rejected input.
                        raw.close()
                finally:
                    for fd in descriptors:
                        try:
                            os.close(fd)
                        except OSError:
                            pass
        except (OSError, ValueError):
            pass  # No raw protocol/dependency data escapes to logs or callers.
        finally:
            self.withdraw()
