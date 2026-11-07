"""Published Ken through current broker domains: local models, fresh sources and zero account use."""

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def prepare_index(trial, installation, model_cache, *, operation_key='prepare', output_prefix='prepare'):
    """Prepare retrieval through its original broker, with distinct operation/output identities when validating multiple source revisions."""
    peer = await asyncio.to_thread(trial.peers.registry.prepare, trial.lease, 'ken')
    endpoint = trial.owner.ken(trial.peers.registry, peer, operation_key=operation_key,
                               installation=installation, model_cache=model_cache, mode='prepare')
    async with asyncio.timeout(90):
        try:
            await endpoint.open(limit=65536)
            stdout, stderr = await asyncio.gather(endpoint.stdout.read(), endpoint.stderr.read())
            (trial.root / (output_prefix + '.stdout')).write_bytes(stdout)
            (trial.root / (output_prefix + '.stderr')).write_bytes(stderr)
            native_exit = await asyncio.to_thread(endpoint._raw.wait, timeout=3)
            receipt = {'exit_code': native_exit,
                       'memory_peak_bytes': int((trial.domain_path / 'memory.peak').read_text()),
                       'memory_events': (trial.domain_path / 'memory.events').read_text()}
            (trial.root / (output_prefix + '-receipt.json')).write_text(json.dumps(receipt, indent=2) + '\n')
            assert native_exit == 0, 'Ken preparation failed; inspect private receipt/log'
        finally:
            closed = await endpoint.aclose(timeout=5)
            assert closed and closed.get('execution_closed') is True
    assert trial.peers.registry.inspect(peer)['state'] == 'closed'
    return closed


async def visit(trial, installation, model_cache, operation, *, operation_key='mcp'):
    """Use the MCP SDK on the original broker pipes with an explicit operation identity, without a secondary launcher."""
    from backend.runtime.broker_mcp import broker_mcp

    peer = await asyncio.to_thread(trial.peers.registry.prepare, trial.lease, 'ken')
    endpoint = trial.owner.ken(trial.peers.registry, peer, operation_key=operation_key,
                               installation=installation, model_cache=model_cache)
    async with broker_mcp(endpoint, request_timeout=30) as session:
        await operation(session)
    assert trial.peers.registry.inspect(peer)['state'] == 'closed'


async def remember(session, content):
    """Store a distinguishable finding under the same topic in independent workspace state."""
    response = await session.call_tool('ken_remember', {'topic': 'shared-topic',
        'content': content, 'anchor_file': 'invoice.py'})
    assert not response.isError, response


async def main(args):
    """Probe published Ken with fresh beta/alpha owners, independent memories and real closure."""
    from backend.runtime.ken_worker import KEN_VERSION, KenInstallation
    from backend.runtime.peer_broker import BrokerLimits
    from evals.runtime.kernel_trial import prepare

    root = REPO / '.researcher/evaluations' / ('ken-isolation-' + uuid4().hex[:8])
    root.mkdir(mode=0o700, parents=True)
    result = {'status': 'starting', 'model_turns_submitted': 0, 'ken_version': KEN_VERSION,
              'local_embeddings': True, 'composition': 'owner.ken/broker_mcp', 'checks': []}
    print('Published Ken isolation:', root, flush=True)
    trials = []
    try:
        installation = await asyncio.to_thread(KenInstallation.inspect, args.ken_command)
        limits = BrokerLimits(memory_bytes=args.memory_mib * 1024**2)
        result['memory_limit_bytes'] = limits.memory_bytes
        alpha = prepare(root / 'alpha', args.codex_binary, args.cgroup_parent, broker_limits=limits)
        beta = prepare(root / 'beta', args.codex_binary, args.cgroup_parent, project_id=202, task_id=2002, broker_limits=limits)
        trials = [alpha, beta]
        originals = {}
        for trial, marker in ((alpha, 'ALPHA_ONLY'), (beta, 'OTHER_PROJECT_SECRET_7f7')):
            source = trial.workspace / 'invoice.py'
            source.write_text('"""Synthetic workspace identity for isolation evaluation."""\n\ndef marker():\n    """Return the local workspace marker."""\n    return ' + repr(marker) + '\n')
            originals[str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
            subprocess.run(['git', 'init', '-q', str(trial.workspace)], check=True, capture_output=True)
        (root / 'owner.key').write_text('FAKE_OWNER_CONTROL_SECRET_8a2')
        async with beta.open():
            await prepare_index(beta, installation, args.model_cache)
            await visit(beta, installation, args.model_cache, lambda session: remember(session, 'OTHER_PROJECT_SECRET_7f7'))

        async def checks(session):
            """Check own-source retrieval and independent memory against foreign paths and symlinks."""
            catalog = {tool.name for tool in (await session.list_tools()).tools}
            assert {"ken_find", "ken_read", "ken_recall", "ken_related"} <= catalog
            own = await session.call_tool(
                "ken_read",
                {
                    "path": "invoice.py",
                    "include": ["source"],
                    "start_line": 1,
                    "end_line": 6,
                },
            )
            assert not own.isError and "ALPHA_ONLY" in own.model_dump_json(), own
            result["checks"].append(
                {"check": "own-source-positive-control", "status": "passed"}
            )
            semantic = await session.call_tool('ken_find', {
                'query': 'Function returning the local workspace marker', 'scope': 'symbols',
                'piece_kind': 'symbol', 'max_chars': 4000,
            })
            assert not semantic.isError and 'marker' in semantic.model_dump_json(), semantic
            result['checks'].append({'check': 'own-semantic-search', 'status': 'passed'})
            structural_query = 'language "kql/2"; module isolation; query q { callable $f { name: "marker"; } select $f.name, $f.path; }'
            for scope, query, extra in (
                ('text', 'ALPHA_ONLY', {'literal': True}),
                ('structure', structural_query, {'query_language': 'kql/2'}),
            ):
                control = await session.call_tool('ken_find', {'scope': scope, 'query': query, **extra})
                assert not control.isError and 'invoice.py' in control.model_dump_json(), control
                result['checks'].append({'check': 'own-' + scope + '-search', 'status': 'passed'})
            for name, params in [
                (
                    "ken_read",
                    {
                        "path": str(beta.workspace / "invoice.py"),
                        "include": ["source"],
                        "start_line": 1,
                        "end_line": 6,
                    },
                ),
                (
                    "ken_read",
                    {
                        "path": "escape.py",
                        "include": ["source"],
                        "start_line": 1,
                        "end_line": 6,
                    },
                ),
                (
                    "ken_read",
                    {
                        "path": "owner.key",
                        "include": ["source"],
                        "start_line": 1,
                        "end_line": 6,
                    },
                ),
                (
                    "ken_find",
                    {
                        "scope": "text",
                        "query": "return",
                        "literal": True,
                        "path": str(beta.workspace),
                    },
                ),
                (
                    "ken_find",
                    {
                        "scope": "structure",
                        "path": str(beta.workspace),
                        "query": structural_query,
                        "query_language": "kql/2",
                        "limit": 1,
                        "timeout_ms": 500,
                    },
                ),
                (
                    "ken_related",
                    {"relation": "imports", "target": str(beta.workspace / "invoice.py")},
                ),
                ("ken_recall", {"topic": "shared-topic"}),
                ("ken_recall", {"path": str(beta.workspace / "invoice.py")}),
            ]:
                answer = await session.call_tool(name, params)
                data = answer.model_dump_json()
                assert "OTHER_PROJECT_SECRET_7f7" not in data, (name, params, data)
                assert "FAKE_OWNER_CONTROL_SECRET_8a2" not in data, (name, params, data)
                if name == "ken_recall" and params.get("topic"):
                    assert "ALPHA_ONLY finding" in data, data
                result["checks"].append(
                    {
                        "tool": name,
                        "arguments": params,
                        "is_error": bool(answer.isError),
                        "foreign_secret_present": False,
                    }
                )


        async def alpha_operation(session):
            """Write alpha's own topic, then verify positive retrieval and all foreign-source denials."""
            await remember(session, 'ALPHA_ONLY finding')
            await checks(session)

        async with alpha.open():
            await prepare_index(alpha, installation, args.model_cache)
            (alpha.workspace / 'escape.py').symlink_to(beta.workspace / 'invoice.py')
            (alpha.workspace / 'owner.key').symlink_to(root / 'owner.key')
            await visit(alpha, installation, args.model_cache, alpha_operation)
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in originals.items())
        result.update(status='passed', original_sources_unchanged=True, independent_memories=True)
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        result['lifecycles'] = [json.loads((trial.root / 'lifecycle.json').read_text()) for trial in trials if (trial.root / 'lifecycle.json').exists()]
        (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'status': result['status'], 'model_turns_submitted': 0}), flush=True)
    assert len(result['lifecycles']) == 2 and all(r['domain_removed'] and r['all_peers_closed'] for r in result['lifecycles'])


if __name__ == '__main__':
    from evals.runtime.kernel_trial import arguments

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True, help='Real local Ken processes; no generative model or account')
    parser.add_argument('--ken-command', type=Path, required=True)
    parser.add_argument('--model-cache', type=Path, required=True)
    parser.add_argument('--memory-mib', type=int, required=True, help='Explicit host memory ceiling for local Ken retrieval models')
    asyncio.run(main(arguments(parser)))
