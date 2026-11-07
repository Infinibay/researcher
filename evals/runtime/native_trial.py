"""Fresh native evaluation installations with explicit resources and observed service closure.

Scenarios share the installed product launcher, never a copied authority or a
prototype runtime profile. Private output retains incomplete attempts for inspection.
"""

import json
import socket
import sqlite3
from contextlib import asynccontextmanager, closing
from dataclasses import dataclass
from pathlib import Path

import httpx

FIXTURE = Path(__file__).with_name('fixture')


@dataclass(frozen=True)
class NativeTrial:
    """Identify the private evidence, fresh installation and synthetic source of one scenario."""

    root: Path
    installation: Path
    database: Path
    workspace: Path
    fixture: Path = FIXTURE


def _seed(trial, *, task_type='research', task_title='Fictional policy explanation', task_context=None):
    """Insert initial synthetic context without creating a timestamped metadata-correction history."""
    trial.workspace.mkdir(mode=0o700)
    for name in ('invoice.py', 'test_invoice.py'):
        (trial.workspace / name).write_bytes((FIXTURE / name).read_bytes())
    with closing(sqlite3.connect(trial.database)) as db, db:
        if db.execute('SELECT COUNT(*) FROM projects').fetchone()[0]:
            raise ValueError('Native evaluation requires an empty synthetic database')
        for project, task, marker in ((101, 1001, 'ALPHA_ONLY'), (202, 2002, 'BETA_ONLY')):
            db.execute('INSERT INTO projects(id,name) VALUES(?,?)', (project, 'Synthetic research ' + marker))
            db.execute("INSERT INTO tasks(id,project_id,type,title,status,created_by,context_json) VALUES(?,?,?,?,'in_progress','user',?)", (task, project, task_type, task_title, json.dumps(task_context) if task_context is not None else None))
            folder = trial.installation / 'uploads' / str(project) / 'uploads'
            folder.mkdir(parents=True, mode=0o700)
            source = folder / 'policy.md'
            source.write_text(f'# Fictional policy {marker}\nTax rates are fractions: 0.21 means 21 percent. Round once at the end using ROUND_HALF_UP.\n')
            db.execute("INSERT INTO reference_files(project_id,file_name,file_path,file_size,file_type) VALUES(?,'policy.md',?,?,'text/markdown')", (project, str(source), source.stat().st_size))
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'synthetic-invoice',?)", (str(trial.workspace),))


def prepare(root, assets_path, *, live, turns, wall_seconds=180, no_progress_seconds=90,
            task_type='research', task_title='Fictional policy explanation', task_context=None):
    """Create one private synthetic installation, preserving operator limits and partial failures.

    --live authorizes this bounded scenario; assets must permit its turn count.
    Model/account paths are retained, while authority and sources are always new.
    The supplied resource file is never edited or interpreted as an installation.
    """
    from backend.runtime.host_installation import _read_json, initialize_host

    if not live:
        raise ValueError('Only --live authorizes a native subscription evaluation')
    if turns not in (1, 2):
        raise ValueError('Native evaluation scenarios admit one or two turns')
    assets = _read_json(assets_path)
    if {'authority', 'runtime_profile', 'control_root', 'workspace_root'} & assets.keys():
        raise ValueError('Supply host assets, never a previous installation or authority')
    if assets.get('project_turn_limit', turns) < turns:
        raise ValueError('Host assets must explicitly permit the scenario turn budget')
    ceilings = {'wall_seconds': wall_seconds, 'no_progress_seconds': no_progress_seconds,
                'max_turns': 1, 'max_tool_calls': 20, 'max_observed_tokens': 350000,
                'max_answer_bytes': 20000}
    limits = dict(assets.get('limits', {}))
    limits.update({key: min(limits.get(key, cap), cap) for key, cap in ceilings.items()})
    assets.update(limits=limits, project_turn_limit=turns,
                  project_token_limit=min(assets.get('project_token_limit', turns * limits['max_observed_tokens']), turns * limits['max_observed_tokens']))
    root = Path(root).absolute()
    root.mkdir(mode=0o700, parents=True)
    installation = root / 'installation'
    trial = NativeTrial(root, installation, installation / 'source.db', installation / 'sources' / 'invoice')
    result = {'status': 'preparing', 'generation_limit': turns, 'model': assets['model']}
    try:
        initialize_host(installation, witness_dir=root / 'witness', assets=assets)
        _seed(trial, task_type=task_type, task_title=task_title, task_context=task_context)
        result['status'] = 'prepared'
        return trial
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        (root / 'preparation.json').write_text(json.dumps(result, indent=2) + '\n')


@asynccontextmanager
async def backend(trial, evidence, *, starter=None):
    """Serve fresh storage with the normal or explicit evaluation starter; always record original process closure."""
    from evals.operation import host_smoke
    from backend.research.sqlite_store import SQLiteResearchStore

    with socket.socket() as binding:
        binding.bind(('127.0.0.1', 0))
        port = binding.getsockname()[1]
    api = f'http://127.0.0.1:{port}'
    process = log = None
    lifecycle = {'owned_backend_terminal': False}
    try:
        process, log = (starter or host_smoke.start)(trial.installation, trial.root, port, 1)
        async with httpx.AsyncClient(base_url=api, timeout=15, trust_env=False) as owner:
            keys = list((trial.installation / 'auth').glob('owner-*.key'))
            if len(keys) != 1:
                raise RuntimeError('Expected one pairing file for this synthetic installation')
            response = await owner.post('/api/session', json={'code': keys[0].read_text().strip()}, headers={'X-Researcher-Client': 'web'})
            response.raise_for_status()
            owner.headers['X-Researcher-CSRF'] = response.json()['csrf_token']
            yield SQLiteResearchStore(trial.database), owner, api, trial.database
    finally:
        try:
            if process is not None:
                lifecycle['service_exit'] = host_smoke.stop(process, log)
                lifecycle['owned_backend_terminal'] = True
        finally:
            evidence.update(lifecycle)
            (trial.root / 'service-lifecycle.json').write_text(json.dumps(lifecycle, indent=2) + '\n')


def arguments(parser):
    """Require an explicit live scenario and host resource file, never a copied runtime config."""
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--assets', type=Path, required=True, help='Host resources with model, subscription path, Ken and scenario budget')
    return parser.parse_args()
