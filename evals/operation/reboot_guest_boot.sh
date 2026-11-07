#!/bin/sh
# The portable Python loader needs /proc/self/exe to expand its $ORIGIN library.
# This shell is only PID1 in the explicitly marked disposable initramfs.
if [ "$$" != 1 ] || [ ! -f /RESEARCHER_DISPOSABLE_VM ]; then
    exit 96
fi
/bin/mount -n -t proc proc /proc || exit 97
/bin/mount -n -t devtmpfs devtmpfs /dev || exit 98
exec /python/bin/python3.12 -S /guest_init.py
