"""Run selected previously observed failures once as development regressions, never as held-out confirmation."""

import argparse
import asyncio
import json
from pathlib import Path

from backend.prompts.native import build_instructions
from backend.runtime.codex_session import ExecutionLimits
from evals.context_alignment.protocol import digest, load_registered
from evals.context_alignment.run import run_arm, save
from evals.profile_communication.cases import CASES, PREFIX

REGRESSION_CASES = ('plan_dependencies', 'skipped_checks', 'selective_outcomes')


def register(root, assets, *, case_ids=None):
    """Freeze selected sources and actual bounded policies before any new attempt; retain operator ceilings."""
    selected = tuple(case_ids) if case_ids is not None else REGRESSION_CASES
    if not selected or len(set(selected)) != len(selected) or set(selected) - set(REGRESSION_CASES):
        raise ValueError('Select distinct known regression cases')
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    operator = json.loads(assets.read_text())
    cases = [next(c for c in CASES if c['id'] == name) for name in selected]
    manifest = {'purpose': 'Development regressions after observed failures; not paired or held-out efficacy evidence.',
                'maximum_model_turns': len(cases), 'cases': []}
    for case in cases:
        folder = root / case['id']
        folder.mkdir(mode=0o700)
        ceilings = {'wall_seconds': 180, 'no_progress_seconds': 90, 'max_turns': 1,
                    'max_tool_calls': 20, 'max_answer_bytes': 20000,
                    'max_observed_tokens': 120000 if case['id'] == 'plan_dependencies' else 350000}
        limits = {key: min(operator.get('limits', {}).get(key, cap), cap) for key, cap in ceilings.items()}
        limits['max_observed_tokens'] = min(limits['max_observed_tokens'], operator['project_token_limit'])
        files = {'candidate.txt': build_instructions('research', case['task_type'], limits=ExecutionLimits(**limits)),
                 'evidence.py': case['source'], 'reference.md': case['reference'],
                 'case.json': json.dumps({**case, 'split': 'development_regression'}, ensure_ascii=False, indent=2) + '\n'}
        for name, value in files.items():
            (folder / name).write_text(value)
        protocol = {'format': 1, 'task_type': case['task_type'], 'task_title': 'Budget delivery regression: ' + case['id'],
                    'request_prefix': PREFIX, 'reference_file': 'reference.md', 'require_complete_source': True,
                    'files': {name: digest(value.encode()) for name, value in files.items()}, 'limits': limits,
                    'maximum_model_turns': 1, 'allowed_model_receipt_variation': ['run_id', 'attempt_id', 'selected_at'],
                    'human_comprehension': None, 'human_effort_seconds': None,
                    'criteria': case['criteria'], 'purpose': manifest['purpose']}
        save(folder / 'registration.json', protocol)
        (folder / 'registration.sha256').write_text(digest((folder / 'registration.json').read_bytes()) + '\n')
        manifest['cases'].append({'id': case['id'], 'registration_sha256': digest((folder / 'registration.json').read_bytes())})
    save(root / 'registration.json', manifest)


async def run(root, assets, *, case_ids=None):
    """Observe each new original handle serially; never replay a failed or uncertain attempt."""
    register(root, assets, case_ids=case_ids)
    manifest = json.loads((root / 'registration.json').read_text())
    for item in manifest['cases']:
        case = next(c for c in CASES if c['id'] == item['id'])
        folder = root / case['id']
        protocol = load_registered(folder)
        try:
            await run_arm(folder, protocol, case, 'candidate', assets)
        except Exception:
            # Continue to a different planned case only after this handle closed.
            result = json.loads((folder / (case['id'] + '-candidate') / 'result.json').read_text())
            if not result.get('owned_backend_terminal'):
                raise
    print(f"{len(manifest['cases'])} original development attempts observed; inspect retained results, including failures.", flush=True)


def main():
    """Require explicit live resources and refuse an existing experiment directory before model work."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--case', action='append', choices=REGRESSION_CASES)
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required')
    asyncio.run(run(args.output.resolve(), args.assets.resolve(), case_ids=args.case))


if __name__ == '__main__':
    main()
