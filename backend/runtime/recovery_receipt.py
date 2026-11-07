"""Separate bounded activation metadata from complete restoration evidence and explain snapshot limits."""

import hashlib
import json
from pathlib import Path

from backend.runtime.host_installation import _write_new
from backend.runtime.snapshot_files import digest_file, open_file, relative_name

DETAILS_LIMIT = 128 * 1024**2
ENVELOPE_LIMIT = 65536


def snapshot_boundary(receipt):
    """State what a snapshot cannot recover without claiming that later writes were observed or compared."""
    return {
        'snapshot_id': receipt['snapshot_id'],
        'source_schema': receipt.get('database', {}).get('schema_version', receipt.get('source_schema')),
        'post_snapshot_writes': 'not_included',
        'comparison_with_current_source': 'not_performed',
        'transparent_downgrade': False,
        'original_overwritten': False,
        'original_availability': 'not_checked',
        'detail': 'Esta instalación conserva el estado de la copia elegida. No incluye escrituras posteriores ni deshace efectos externos. Este comando no reemplaza el original ni comprueba que siga disponible. Para conservar cambios posteriores, recupera una copia que los incluya o repara el original; no reemplaces la única copia vigente.',
    }


def write_restoration_receipt(root, evidence, receipt, budget):
    """Publish complete relocation evidence and a small hash-bound receipt before the final installation marker."""
    receipt['data_recovery'] = snapshot_boundary(receipt)
    details = root / evidence / 'details.json'
    encoded_size = len((json.dumps(receipt, indent=2) + '\n').encode())
    if encoded_size > DETAILS_LIMIT:
        raise ValueError('Restoration details exceed their explicit 128 MiB bound')
    budget.check(size=encoded_size)
    _write_new(details, receipt)
    observed = digest_file(root, str(details.relative_to(root)), budget)
    budget.bytes += observed['bytes']
    envelope = {
        'format': 2, 'status': 'pending_enrollment',
        'snapshot_id': receipt['snapshot_id'], 'restored_root': receipt['restored_root'],
        'details': {'path': str(details.relative_to(root)), **observed},
    }
    _write_new(root / evidence / 'restoration.json', envelope)


def _bounded_bytes(root, relative, limit):
    """Read one regular metadata file through pinned no-follow parents without truncating oversized evidence."""
    with open_file(root, relative) as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Restoration metadata exceeds its explicit bound')
    return raw


def read_restoration_receipt(root, relative):
    """Accept legacy receipts or verify bounded format2 evidence before creating any execution authority."""
    relative = str(relative_name(relative))
    envelope = json.loads(_bounded_bytes(root, relative, ENVELOPE_LIMIT))
    if not isinstance(envelope, dict):
        raise ValueError('Restoration receipt must be an object')
    if envelope.get('format') == 1:
        receipt = envelope
    elif envelope.get('format') == 2:
        details = envelope['details']
        if not isinstance(details, dict) or set(details) != {'path', 'bytes', 'sha256'}:
            raise ValueError('Restoration details require a path, exact byte count and hash')
        if details['path'] != str(Path(relative).with_name('details.json')):
            raise ValueError('Restoration details must belong to the original receipt directory')
        size = details['bytes']
        if type(size) is not int or not 0 < size <= DETAILS_LIMIT:
            raise ValueError('Restoration details exceed their explicit bound')
        raw = _bounded_bytes(root, details['path'], size)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != details['sha256']:
            raise ValueError('Restoration details changed; preserve evidence and restore to a NEW path')
        receipt = json.loads(raw)
        if not isinstance(receipt, dict) or receipt.get('format') != 1:
            raise ValueError('Unsupported restoration details format')
        if any(receipt.get(key) != envelope.get(key) for key in ('snapshot_id', 'restored_root', 'status')):
            raise ValueError('Restoration details identity differs from its receipt')
    else:
        raise ValueError('Unsupported restoration receipt format')
    if receipt.get('status') != 'pending_enrollment':
        raise ValueError('Restoration receipt is not pending enrollment')
    # Derive the limitation from the operation, never accept a claim of transparent rollback.
    receipt['data_recovery'] = snapshot_boundary(receipt)
    return receipt
