"""Exercise code reading and structural writes through the owned native tool boundary.

Generation and Ken retrieval are controlled; Git, file edits, command peers,
candidate capture, check execution and SQLite receipts are real. These tests
prove composition, not a model's ability to infer a correct refactor.
"""

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from backend.tests.runtime.test_development_session import (
    call_development_tool,
    development_attempt,
    development_config as development_config,
    ken_preparations,
    run_development_turn,
)
from backend.tests.runtime.test_development_workspace import fixture_git
from backend.tests.runtime.test_owned_factory import owned_config as owned_config


ORIGINAL = '''"""Small conversion domain used to observe actual refactoring effects."""

class Converter:
    """Convert a measured value with the fixture's original factor."""

    def convert(self, value):
        """Return the original double value."""
        return value * 2

    def obsolete(self):
        """Represent an unused method explicitly selected for removal."""
        return None
'''
CLIENT = '''"""Consume the conversion API across a module boundary."""
from maths import Converter

def render(value):
    """Return the observed domain result and an unrelated literal."""
    return Converter().convert(value), "convert is a literal"
'''
EDIT = r'''import ast, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
p = Path('maths.py')
tree = ast.parse(p.read_text())
cls = tree.body[1]
assert cls.name == 'Converter'
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'convert')
method.name = 'scale'
method.body = ast.parse('"Return the requested triple value."\nreturn value * 3').body
cls.body = [n for n in cls.body if not isinstance(n, ast.FunctionDef) or n.name != 'obsolete']
cls.body += ast.parse('def describe(self):\n    "Describe the new public operation."\n    return "scale"').body
cls.name = 'Scaler'
ast.fix_missing_locations(tree)
p.write_text(ast.unparse(tree) + '\n')
client = ast.parse(Path('client.py').read_text())
for node in ast.walk(client):
    if isinstance(node, ast.ImportFrom):
        assert node.module == 'maths'
        node.names[0].name = 'Scaler'
    elif isinstance(node, ast.Name) and node.id == 'Converter':
        node.id = 'Scaler'
    elif isinstance(node, ast.Attribute) and node.attr == 'convert':
        node.attr = 'scale'
Path('client.py').write_text(ast.unparse(client) + '\n')
from maths import Scaler
from client import render
assert render(7) == (21, 'convert is a literal')
assert Scaler().describe() == 'scale' and not hasattr(Scaler, 'obsolete')
print('edit add remove rename verified')
'''
MOVE = r'''import ast, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
p = Path('maths.py')
tree = ast.parse(p.read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Scaler')
tree.body.remove(cls)
Path('metrics.py').write_text('"""Own the moved scaling domain."""\n' + ast.unparse(cls) + '\n')
p.write_text(ast.unparse(tree) + '\n')
client = ast.parse(Path('client.py').read_text())
for node in ast.walk(client):
    if isinstance(node, ast.ImportFrom):
        assert node.module == 'maths'
        node.module = 'metrics'
Path('client.py').write_text(ast.unparse(client) + '\n')
from client import render
assert render(-4) == (-12, 'convert is a literal')
print('move and dependent import verified')
'''


async def _tool(session, name, arguments):
    """Read the original native tool reply without substituting a result or replaying an effect."""
    result = await call_development_tool(session, name, arguments)
    assert result['success'], result
    return result['contentItems'][0]['text']


async def _python(session, key, code):
    """Run a private writer and retain its terminal output and physical closure receipt."""
    started = json.loads(await _tool(session, 'researcher_python', {
        'operation_key': key, 'code': code, 'timeout_seconds': 5,
    }))
    async with asyncio.timeout(15):
        while True:
            receipt = json.loads(await _tool(session, 'researcher_command_read', {
                'job_id': started['job_id'], 'wait_ms': 1000,
            }))
            if receipt['status'] == 'exited':
                break
    assert receipt['exit_code'] == 0, receipt['stderr']
    assert receipt['local_execution_closed']
    assert not receipt['stdout']['has_more'] and not receipt['stderr']['has_more']
    return receipt


@pytest.mark.timeout(60)
async def test_native_refactor_updates_callers_and_captures_checked_private_candidate(development_config):
    """Read, edit/add/remove/rename/move, re-read, capture and check without modifying the source or accepting the task."""
    from backend.runtime.check_contracts import CheckSpec

    c = development_config
    async with development_attempt(c) as d:
        (c.s.workspace / 'maths.py').write_text(ORIGINAL)
        (c.s.workspace / 'client.py').write_text(CLIENT)
        await fixture_git(c.s.workspace, 'add', 'maths.py', 'client.py')
        await fixture_git(c.s.workspace, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost', 'commit', '-qm', 'conversion source')
        original_sha = await fixture_git(c.s.workspace, 'rev-parse', 'HEAD')
        async with d.coordinator.runtime.open(workspace=c.s.workspace, tool_token=d.token, peer_owner=d.peers) as session:
            before = await _tool(session, 'ken_read', {'path': 'maths.py'})
            assert before == ORIGINAL
            edited = await _python(session, 'structural-edit', EDIT)
            assert edited['stdout']['text'] == 'edit add remove rename verified\n'
            after = await _tool(session, 'ken_read', {'path': 'maths.py'})
            assert 'class Scaler:' in after and 'def scale(' in after
            assert 'def describe(' in after and 'obsolete' not in after
            moved = await _python(session, 'structural-move', MOVE)
            assert moved['stdout']['text'] == 'move and dependent import verified\n'
            assert 'class Scaler:' in await _tool(session, 'ken_read', {'path': 'metrics.py'})
            assert 'from metrics import Scaler' in await _tool(session, 'ken_read', {'path': 'client.py'})
            assert len(ken_preparations(session)) == 3
            # Controlled generation still uses the actual native transport and closes its own writer.
            assert (await run_development_turn(d, session)).status == 'completed'
            candidate = await session.capture_candidate()
            assert candidate['state'] == 'ready'
            checked = await session.run_check('refactor-behavior', CheckSpec(
                ('/usr/bin/python3', '-B', '-c',
                 "from client import render; from metrics import Scaler; import maths; "
                 "assert render(0)==(0,'convert is a literal'); "
                 "assert render(7)==(21,'convert is a literal'); "
                 "assert render(-4)==(-12,'convert is a literal'); "
                 "assert Scaler().describe()=='scale'; "
                 "assert not hasattr(Scaler,'obsolete') and not hasattr(maths,'Scaler')"),
                'command', timeout_seconds=5, environment_id='system',
            ))
            outcome = json.loads(checked['result_json'])
            assert checked['state'] == 'finished' and outcome['status'] == 'passed'
            assert outcome['subject']['head_sha'] == candidate['head_sha']
            assert (Path(candidate['workspace']) / 'metrics.py').is_file()
        await d.peers.aclose()
        assert d.coordinator.runtime.consume_closure(d.lease)
        assert all(row['state'] == 'closed' for row in d.peers._rows())
        assert (c.s.workspace / 'maths.py').read_text() == ORIGINAL
        assert (c.s.workspace / 'client.py').read_text() == CLIENT
        assert not (c.s.workspace / 'metrics.py').exists()
        assert await fixture_git(c.s.workspace, 'rev-parse', 'HEAD') == original_sha
        assert not await fixture_git(c.s.workspace, 'status', '--porcelain')
        assert c.s.c.conn.execute('SELECT status FROM tasks WHERE id=1001').fetchone()[0] != 'done'


def test_native_installation_has_no_second_code_index_or_legacy_file_executor():
    """Only the selected native owner may execute code operations; old import paths cannot revive the retired stack."""
    for name in ('backend.code_intel', 'backend.tools.code_intel', 'backend.tools.file',
                 'backend.cli.initial_index', 'backend.cli.index_queue'):
        assert importlib.util.find_spec(name) is None, name
