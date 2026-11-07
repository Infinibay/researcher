"""Pure bounded projections and selective JSON evidence views; references preserve exact content identity and never imply that omitted bytes were read."""

import hashlib

from backend.knowledge.reviews import canonical
from backend.runtime.contracts import RunConflict

WORK_SECTIONS = ('plan_context', 'continuation', 'reauthorization')
MAX_INLINE_CONTEXT_BYTES = 32768
MAX_INDEX_CHILDREN = 25


def describe_value(value):
    """Identify exact canonical JSON bytes and shape without copying content or making a semantic comprehension claim."""
    data = canonical(value).encode()
    kind = 'object' if isinstance(value, dict) else 'array' if isinstance(value, list) else 'scalar'
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'kind': kind}


def project_delivery(packet):
    """Keep current task authority visible and replace only large historical sections in new deliveries; older schemas remain byte-equivalent."""
    if packet['schema_version'] < 5:
        return packet
    result = dict(packet)
    result['delivery_packet_sha256'] = describe_value(packet)['sha256']
    for section in WORK_SECTIONS:
        if section not in packet:
            continue
        descriptor = describe_value(packet[section])
        if descriptor['bytes'] > MAX_INLINE_CONTEXT_BYTES:
            result[section] = {'material_reference': {
                'read_tool': 'researcher_work_context', 'section': section, **descriptor,
                'authority': 'attributed_context', 'content_read': False,
                'read_before_reliance': True,
            }}
    return result


def select_material(value, *, path=(), mode='read', child_offset=0):
    """Select one exact JSON value or a bounded child index; keys navigate stored data only, never Python attributes, paths or another authority scope."""
    if not isinstance(path, (tuple, list)) or len(path) > 16:
        raise ValueError('Use at most16 JSON object keys or array indices')
    if mode not in ('read', 'inspect') or type(child_offset) is not int or child_offset < 0:
        raise ValueError('Use read or inspect with a nonnegative child_offset')
    if mode == 'read' and child_offset:
        raise ValueError('child_offset is only valid when inspecting children')
    for key in path:
        if not ((type(key) is str and len(key.encode()) <= 256) or (type(key) is int and key >= 0)):
            raise ValueError('Use exact object keys or nonnegative integer array indices')
        if isinstance(value, dict) and type(key) is str and key in value:
            value = value[key]
        elif isinstance(value, list) and type(key) is int and key < len(value):
            value = value[key]
        else:
            raise RunConflict('Selected material path does not exist in this bound section')
    if mode == 'inspect':
        keys = sorted(value) if isinstance(value, dict) else range(len(value)) if isinstance(value, list) else ()
        if child_offset > len(keys):
            raise ValueError('Child offset exceeds this value\'s child count')
        end = min(len(keys), child_offset + MAX_INDEX_CHILDREN)
        value = {
            **describe_value(value), 'content_read': False, 'children_total': len(keys),
            'child_offset': child_offset, 'next_child_offset': end if end < len(keys) else None,
            'children': [{'key': key, **describe_value(value[key])} for key in keys[child_offset:end]],
        }
    return canonical(value).encode()
