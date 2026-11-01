"""Trusted one-byte exec gate, launched inside the private PID namespace."""

import os
import select
import sys


def main():
    if not select.select([0], [], [], 15)[0] or os.read(0, 1) != b"G":
        sys.exit(125)
    os.execvpe(sys.argv[1], sys.argv[1:], os.environ)


if __name__ == "__main__":
    main()
