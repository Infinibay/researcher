"""Reuse the installed paired evaluator for predeclared planning, science and audit cases.

Registration is account-free. Every live arm is fresh, bounded and admitted once;
failed or incomplete arms remain evidence, not candidates for automatic replay.
"""

import argparse
import asyncio
import json
from pathlib import Path

from evals.context_alignment.protocol import digest, load_registered
from evals.context_alignment.run import compare_pair, export_review, run_arm, save
from evals.profile_communication.cases import CASES, PREFIX

ROOT = Path(__file__).resolve().parents[2]


def register(root, *, cases=CASES, token_limit=120000, prior_registration=None):
    """Freeze every policy, source, case and rubric before any outcome can influence the study."""
    from backend.prompts.native import build_instructions

    if not 1 <= token_limit <= 350000 or not cases or len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Invalid evaluation cases or token ceiling')
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    baseline = json.loads((ROOT / 'evals/prompts/baseline.json').read_text())
    manifest = {'format': 1, 'maximum_model_turns': 2 * len(cases), 'cases': [], 'prior_registration': prior_registration,
                'scope': 'Four purposive synthetic cases; no population effect, statistical efficacy or human-comprehension inference.'}
    for case in cases:
        index = next(i for i, original in enumerate(CASES) if original['id'] == case['id'])
        folder = root / case['id']
        folder.mkdir(mode=0o700)
        contents = {'baseline.txt': baseline['instructions'][case['profile']],
                    'candidate.txt': build_instructions('research', case['task_type']),
                    'evidence.py': case['source'], 'reference.md': case['reference'],
                    'case.json': json.dumps(case, ensure_ascii=False, indent=2) + '\n'}
        for name, content in contents.items():
            (folder / name).write_text(content)
        protocol = {
            'format': 1, 'case': case, 'profile': case['profile'], 'task_type': case['task_type'],
            'task_title': 'Communication evaluation: ' + case['id'], 'baseline_commit': baseline['source_commit'],
            'request_prefix': PREFIX, 'reference_file': 'reference.md', 'require_complete_source': True,
            'files': {name: digest(content.encode()) for name, content in contents.items()},
            'order': ['baseline', 'candidate'] if index % 2 == 0 else ['candidate', 'baseline'],
            'maximum_model_turns': 2, 'allowed_model_receipt_variation': ['run_id', 'attempt_id', 'selected_at'],
            'limits': {'wall_seconds': 180, 'no_progress_seconds': 90, 'max_tool_calls': 20, 'max_observed_tokens': token_limit},
            'controls': ['exact same substantive frozen input', 'same model/effort and tools', 'same code/attachment bytes'],
            'rubric': case['criteria'],
            'human_comprehension': None, 'human_effort_seconds': None,
            'rejection': 'Invalid controls or unclosed original peers invalidate the pair; record capability/authority violations separately from textual quality.',
        }
        save(folder / 'registration.json', protocol)
        fingerprint = digest((folder / 'registration.json').read_bytes())
        (folder / 'registration.sha256').write_text(fingerprint + '\n')
        manifest['cases'].append({'id': case['id'], 'split': case['split'], 'registration_sha256': fingerprint})
    save(root / 'registration.json', manifest)
    (root / 'registration.sha256').write_text(digest((root / 'registration.json').read_bytes()) + '\n')
    return manifest


def registered(root):
    """Verify the entire preregistration before selecting even one live arm."""
    raw = (root / 'registration.json').read_bytes()
    if digest(raw) != (root / 'registration.sha256').read_text().strip():
        raise ValueError('Study registration changed')
    manifest = json.loads(raw)
    for case in manifest['cases']:
        folder = root / case['id']
        if digest((folder / 'registration.json').read_bytes()) != case['registration_sha256']:
            raise ValueError('Case registration changed')
        load_registered(folder)
    return manifest


async def run(args):
    """Run only a selected unstarted pair, preserving original handles and refusing silent replay."""
    manifest = registered(args.output)
    selected = [case for case in manifest['cases'] if case['split'] == args.split and (not args.case or case['id'] == args.case)]
    if not selected:
        raise ValueError('No registered case in the selected split')
    assets_hash = digest(args.assets.read_bytes())
    for item in selected:
        folder = args.output / item['id']
        protocol = load_registered(folder)
        case = protocol['case']
        for arm in protocol['order']:
            if (folder / (case['id'] + '-' + arm)).exists():
                raise FileExistsError('Pair already started; inspect original receipts instead of replaying')
        pair = {}
        for arm in protocol['order']:
            registered(args.output)
            if digest(args.assets.read_bytes()) != assets_hash:
                raise ValueError('Host resources changed during comparison')
            pair[arm] = await run_arm(folder, protocol, case, arm, args.assets)
            attempt = pair[arm]['attempts']
            if len(attempt) != 1 or attempt[0]['instructions_sha256'] != protocol['files'][arm + '.txt']:
                raise ValueError('Actual policy or turn count differs from registration')
        comparison = compare_pair(pair['baseline'], pair['candidate'])
        save(folder / 'comparison.json', comparison)
        export_review(folder, case, pair)
        print('Pair controls verified', case['id'], flush=True)


def main():
    """Separate account-free preparation from explicitly authorized bounded subscription runs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--assets', type=Path)
    parser.add_argument('--split', choices=('development', 'reserved'), default='development')
    parser.add_argument('--case')
    args = parser.parse_args()
    args.output = args.output.absolute()
    if args.prepare:
        register(args.output)
        print('Registered', args.output)
        return
    if not args.live or args.assets is None:
        parser.error('--live and --assets required')
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
