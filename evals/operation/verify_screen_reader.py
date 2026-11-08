"""Verify retained Orca and Speech Dispatcher protocol evidence independently of the GUI-driving assertions."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def read_log(path):
    """Read original bytes or their lossless archive, preserving producer byte offsets."""
    return path.read_bytes() if path.exists() else gzip.decompress(path.with_suffix(path.suffix + '.gz').read_bytes())


def normalized(text):
    """Compare spoken words with whitespace/case normalization, without discarding punctuation or decorative symbols."""
    return ' '.join(unicodedata.normalize('NFC', text).casefold().split())


def module_frames(data):
    """Parse actual module SSML and END boundaries; queued or cancelled speech alone is insufficient."""
    matches = list(re.finditer(rb'Command sent to output module: \|(<speak>.*?</speak>)\|', data, re.S))
    frames = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(data)
        frames.append({'start': match.start(), 'end': match.end(),
                       'text': ''.join(ET.fromstring(match.group(1)).itertext()),
                       'completed': b'702 END' in data[match.end():end]})
    return frames


def verify(evaluation, require_current_source=False):
    """Require current route/text evidence, clean child/container closure and unchanged observed durable records; do not certify other readers/content."""
    result = json.loads((evaluation / 'result.json').read_text())
    browser = json.loads((evaluation / 'browser/browser-result.json').read_text())
    reader = json.loads((evaluation / 'browser/reader-result.json').read_text())
    assert result['status'] == browser['status'] == reader['status'] == 'passed'
    assert result['container_exit'] == result['container_cleanup_exit'] == 0
    assert result['business_and_inference_unchanged'] and result['storage_before'] == result['storage_after_close']
    assert result['pairing_code_absent_from_logs'] and reader['pairing_before_reader']
    assert reader['browser_exit'] == 0 and all(child['exit'] == 0 for child in reader['children'])
    assert result['storage_after_close']['integrity'] == 'ok'
    assert result['storage_after_close']['runs'] == result['storage_after_close']['dispatches'] == result['storage_after_close']['native_starts'] == 0
    assert len(browser['routes']) == 12 and len({row['route'] for row in browser['routes']}) == 12
    assert len(browser['content']) == 2 and not browser['pageErrors'] and not browser['apiErrors']
    raw_orca = read_log(evaluation / 'browser/orca-debug.log')
    raw_speech = read_log(evaluation / 'browser/speech-logs/speech-dispatcher.log')
    frames = module_frames(raw_speech)
    matched = []
    role_checks = []

    def check_phrase(proof):
        """Correlate a fresh recorded Orca output with independently parsed, completed module text."""
        mode = proof['mode']
        assert mode in ('single', 'say-all')
        assert proof['moduleEnd']
        actual_output = proof['orcaOutput'].encode()
        assert actual_output in raw_orca[proof['start']['orca']:]
        if mode == 'single':
            assert actual_output.startswith(b'SPEECH OUTPUT:') or b' - SPEECH OUTPUT:' in actual_output
            assert 'SPEECH OUTPUT HOOK:' not in proof['orcaOutput']
            assert normalized(proof['phrase']) in normalized(proof['orcaOutput'])
        else:
            assert actual_output.startswith(b'SPEECH DISPATCHER: Speaking ')
            ssml = re.search(rb'(<speak>.*?</speak>)', actual_output, re.S)
            assert ssml is not None
            assert normalized(proof['phrase']) in normalized(''.join(ET.fromstring(ssml.group(1)).itertext()))
        candidates = [(index, frame) for index, frame in enumerate(frames)
                      if frame['start'] >= proof['start']['speech'] and frame['completed']
                      and normalized(frame['text']) == normalized(proof['moduleText'])
                      and normalized(proof['phrase']) in normalized(frame['text'])]
        assert candidates, proof['phrase']
        index, frame = candidates[0]
        matched.append({'phrase': proof['phrase'], 'mode': mode, **frame})
        return index

    for row in browser['routes']:
        focus = row['focusSpeech']
        assert focus['event'].encode() in raw_orca[focus['start']['orca']:]
        source = re.split(r'(?:EVENT )?ANY DATA', focus['event'])[0]
        assert re.search(r"states='[^']*\bfocused\b", source)
        target = focus['target']
        if target['id']:
            assert 'id:' + target['id'] in source
        else:
            assert 'tag:' + target['tag'] in source and "name='" + target['name'] + "'" in source
        assert row['navigationSpeech']['phrase'] == row['label']
        assert row['controlSpeech']['phrase'] == row['controlLabel']
        assert row['headingSpeech']['phrase'] == row['heading']
        for key in ['navigationSpeech', 'controlSpeech', 'browseModeSpeech']:
            check_phrase(row[key])
        index = check_phrase(row['headingSpeech'])
        # Orca51 may synthesize the title and role using separate voices; require the adjacent completed heading-one role.
        roles = [frame for frame in frames[index:index + 2] if frame['completed'] and re.search(r'\bheading\s+(?:level\s+)?1\b', normalized(frame['text']))]
        assert roles, ('missing completed heading-one role', row['route'])
        role_checks.append({'route': row['route'], 'role_frame': roles[0]})
    for proof in browser['content']:
        check_phrase(proof)
    sources = {}
    for relative in ['frontend/tests/screen-reader-audit.mjs', 'evals/operation/screen_reader.py', 'evals/operation/screen_reader_container.py']:
        retained = (evaluation / 'sources' / relative).read_bytes()
        sources[relative] = {'sha256': hashlib.sha256(retained).hexdigest(), 'matches_current_worktree': (ROOT / relative).read_bytes() == retained}
    if require_current_source:
        assert all(value['matches_current_worktree'] for value in sources.values())
    return {'status': 'verified_scoped', 'scope': browser['scope'], 'routes': 12, 'reader_focus_events': 12,
            'completed_phrase_checks': len(matched), 'distinct_matched_module_frames': len({frame['start'] for frame in matched}),
            'heading_one_role_checks': role_checks, 'phrase_evidence': matched, 'source': sources,
            'tools': reader['tools'], 'model_turns': 0, 'observed_business_and_inference_unchanged': True, 'pairing_code_absent_from_logs': True,
            'remaining': ['Rich explanation and diagram reader coverage', 'Physical listening, other readers/viewport combinations and human comprehension not established', 'Whole-project final acceptance remains open']}


def main():
    """Write a new verifier receipt from raw or losslessly archived reader logs, without starting services or a browser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-current-source', action='store_true')
    args = parser.parse_args()
    result = verify(args.evaluation, args.require_current_source)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps({key: result[key] for key in ['status', 'routes', 'completed_phrase_checks', 'distinct_matched_module_frames']}))


if __name__ == '__main__':
    main()
