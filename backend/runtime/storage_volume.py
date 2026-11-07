"""Bind durable host writes to an operator-provisioned, capacity-bounded ext4 volume.

The kernel filesystem, not a periodic directory scan, enforces aggregate blocks
and inodes. This module never mounts, formats, resizes, repairs or deletes data.
Provisioning and privileged mount changes belong to the operator. Missing or
changed storage is an error, never an invitation to initialize a replacement.
"""

import os
from pathlib import Path
import re

from backend.runtime.contracts import RunConflict


def _unescape(value):
    """Decode the octal escapes used for paths in Linux mountinfo."""
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)


def _mounts():
    """Read actual mount identities, retaining separate mount and superblock options."""
    result = []
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        before, after = line.split(' - ', 1)
        fields, filesystem = before.split(), after.split()
        result.append({
            'device': fields[2], 'root': _unescape(fields[3]),
            'path': Path(_unescape(fields[4])), 'options': fields[5].split(','),
            'kind': filesystem[0], 'super_options': filesystem[2].split(','),
        })
    return result


def _policy(value):
    """Validate an explicit volume and capacity ceiling without coercing booleans or paths."""
    if not isinstance(value, dict) or set(value) != {'mount', 'max_bytes', 'admission_free_bytes'}:
        raise ValueError('Storage requires mount, max_bytes and admission_free_bytes')
    if not isinstance(value['mount'], str) or not Path(value['mount']).is_absolute():
        raise ValueError('Storage mount must be an absolute path')
    maximum, margin = value['max_bytes'], value['admission_free_bytes']
    if type(maximum) is not int or not 64 * 1024**2 <= maximum <= 1024**4:
        raise ValueError('Storage capacity must be an integer from 64 MiB to 1 TiB')
    if type(margin) is not int or not 1024**2 <= margin <= maximum // 2:
        raise ValueError('Storage admission margin must be from 1 MiB to half the capacity')
    return dict(value)


def _observe(policy):
    """Observe a dedicated kernel ext4 mount and its whole block-device capacity."""
    mount = Path(policy['mount'])
    if mount == Path('/') or mount.resolve(strict=True) != mount:
        raise ValueError('Storage needs a dedicated canonical mount, not the host root')
    mounts = _mounts()
    selected = [entry for entry in mounts if entry['path'] == mount]
    if len(selected) != 1:
        raise ValueError('Storage mount is missing or stacked; preserve existing data')
    entry = selected[0]
    if entry['kind'] != 'ext4' or entry['root'] != '/':
        raise ValueError('Storage requires a whole dedicated ext4 filesystem')
    if 'rw' not in entry['options'] or 'rw' not in entry['super_options']:
        raise ValueError('Storage volume is read-only')
    if any(item['path'] != mount and item['path'].is_relative_to(mount) for item in mounts):
        raise ValueError('Nested mounts can escape the storage bound')
    fd = os.open(mount, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info, capacity = os.fstat(fd), os.fstatvfs(fd)
        if f'{os.major(info.st_dev)}:{os.minor(info.st_dev)}' != entry['device']:
            raise ValueError('Storage mount changed while checking its identity')
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Storage mount must be private and owned by the serving user')
        device_bytes = int((Path('/sys/dev/block') / entry['device'] / 'size').read_text()) * 512
        filesystem_bytes = capacity.f_blocks * capacity.f_frsize
        if not 0 < filesystem_bytes <= device_bytes <= policy['max_bytes']:
            raise ValueError('Storage device exceeds the configured aggregate capacity')
        if capacity.f_flag & os.ST_RDONLY or capacity.f_files <= 0:
            raise ValueError('Storage has no writable bounded inode space')
        receipt = {
            'policy': policy, 'device': info.st_dev, 'inode': info.st_ino,
            'fsid': capacity.f_fsid, 'device_bytes': device_bytes,
            'filesystem_bytes': filesystem_bytes, 'inodes': capacity.f_files,
        }
        available = {'available_bytes': capacity.f_bavail * capacity.f_frsize,
                     'available_inodes': capacity.f_favail}
        if (mount.stat().st_dev, mount.stat().st_ino) != (info.st_dev, info.st_ino):
            raise ValueError('Storage mount identity changed during observation')
        return receipt, available
    finally:
        os.close(fd)


class StorageVolume:
    """Revalidate one original capacity receipt before startup and new work admission."""

    def __init__(self, receipt):
        """Load a bounded receipt; construction neither creates files nor trusts old observations."""
        expected = {'policy', 'device', 'inode', 'fsid', 'device_bytes', 'filesystem_bytes', 'inodes'}
        if not isinstance(receipt, dict) or set(receipt) != expected:
            raise ValueError('Storage receipt is incomplete')
        self.policy = _policy(receipt['policy'])
        if any(type(receipt[name]) is not int or receipt[name] < 0 for name in expected - {'policy'}):
            raise ValueError('Storage receipt has invalid identity or capacity')
        self.receipt = {**receipt, 'policy': self.policy}

    @classmethod
    def capture(cls, policy):
        """Observe a pre-existing operator volume; never treat an ordinary directory as a quota."""
        receipt, _ = _observe(_policy(policy))
        return cls(receipt)

    def check(self, paths=(), *, admission=False):
        """Prove current identity and path coverage; optionally reject low-space new work.

        The free-space margin is only admission policy, not reserved space or the
        hard limit. Even after admitted work fills the filesystem, its kernel
        block/inode limit remains in force. Stop must not call this admission gate.
        """
        current, available = _observe(self.policy)
        if current != self.receipt:
            raise ValueError('Original storage volume or capacity changed; reconcile it explicitly')
        mount = Path(self.policy['mount'])
        for value in paths:
            path = Path(value).absolute()
            if path.resolve() != path or not path.is_relative_to(mount):
                raise ValueError('Mutable host data must stay inside its original storage volume')
            existing = path
            while not existing.exists() and existing != mount:
                existing = existing.parent
            if existing.stat().st_dev != self.receipt['device']:
                raise ValueError('Mutable host data is on a different filesystem')
        if admission and (available['available_bytes'] < self.policy['admission_free_bytes']
                          or available['available_inodes'] < 128):
            raise RunConflict(
                'No hay espacio suficiente para iniciar trabajo nuevo. '
                'Se conserva el trabajo existente; libera espacio de forma explícita antes de continuar.'
            )
        return {'enforced': True, 'kind': 'dedicated_ext4_volume', **current, **available}


def configured_storage(config, paths=(), *, admission=False):
    """Open an explicit storage policy without silently downgrading a missing receipt.

    Older installations have neither field and remain explicitly unbounded.
    Adding a policy to existing data is not enrollment: a new verified receipt
    must be obtained through explicit host preparation or restored-host enrollment.
    """
    if 'storage' not in config and 'storage_receipt' not in config:
        return None
    volume = StorageVolume(config.get('storage_receipt'))
    if volume.policy != _policy(config.get('storage')):
        raise ValueError('Configured storage policy differs from its original receipt')
    volume.check(paths, admission=admission)
    return volume
