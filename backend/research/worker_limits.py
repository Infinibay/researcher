"""Linux resource bootstrap shared by fixed PDF and local semantic workers."""

import ctypes
import math
import os
import resource
import signal
import sys


def apply_limits(options):
    """Set parent-death, CPU/AS/wall/FD/process/write bounds before third-party imports."""
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


def observed_limits():
    """Report observed execution fuses; these are not a general filesystem/network sandbox."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "peak_rss_kib": usage.ru_maxrss,
        "cpu_used_seconds": usage.ru_utime + usage.ru_stime,
        "cpu_limit_seconds": resource.getrlimit(resource.RLIMIT_CPU)[0],
        "cpu_hard_limit_seconds": resource.getrlimit(resource.RLIMIT_CPU)[1],
        "address_space_limit_bytes": resource.getrlimit(resource.RLIMIT_AS)[1],
    }
