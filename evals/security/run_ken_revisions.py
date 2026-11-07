"""Verify published Ken refreshes changed source in its retained index using installed Researcher, real broker closure and no account or generative turn.

Run with the noneditable environment's Python -I. The operator deliberately
changes only a synthetic source between closed MCP peers; active-writer and
concurrent-refresh refusal belong to the product's separate deterministic tests.
"""

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4

import backend

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def main(args):
    """Keep one real index directory across two source revisions, prove current semantic/read results and retain original physical closure."""
    assert Path(backend.__file__).is_relative_to(Path(sys.prefix)), 'Use noneditable installed Researcher with Python -I'
    from backend.runtime.ken_worker import KEN_VERSION, KenInstallation
    from backend.runtime.peer_broker import BrokerLimits
    from evals.runtime.kernel_trial import prepare
    from evals.security.run_ken_isolation import prepare_index, visit

    root = REPO / '.researcher/evaluations' / ('ken-revisions-' + uuid4().hex[:8])
    root.mkdir(mode=0o700, parents=True)
    result = {'status':'starting', 'ken_version':KEN_VERSION, 'model_turns_submitted':0,
              'backend_module':str(Path(backend.__file__).resolve()), 'revisions':[],
              'scope':'One synthetic Python module, retained index, sequential closed preparation/MCP peers; no general index completeness or concurrent-foreign-writer claim.'}
    print('Published Ken revisions:', root, flush=True)
    trial = None
    try:
        installation = await asyncio.to_thread(KenInstallation.inspect, args.ken_command)
        trial = prepare(root/'trial', args.codex_binary, args.cgroup_parent,
                        broker_limits=BrokerLimits(memory_bytes=args.memory_mib*1024**2))
        source = trial.workspace/'measurement.py'
        index_identity = None
        async with trial.open():
            for number, (symbol, value) in enumerate([('old_measurement',137),('new_measurement',200)], 1):
                source.write_text(f'"""Synthetic measured revision {number}."""\n\ndef {symbol}():\n    """Return the captured measurement {value} from revision {number}."""\n    return {value}\n')
                if index_identity is not None:
                    info = (trial.workspace/'.ken').stat()
                    assert (info.st_dev, info.st_ino) == index_identity
                prefix = f'revision-{number}'
                await prepare_index(trial, installation, args.model_cache, operation_key=prefix+'-prepare', output_prefix=prefix)
                info = (trial.workspace/'.ken').stat()
                current_identity = (info.st_dev, info.st_ino)
                assert index_identity is None or current_identity == index_identity
                index_identity = current_identity
                prepared = json.loads((trial.root/(prefix+'.stdout')).read_text())
                assert prepared['indexed_files'] >= 1 and prepared['profile_version']
                observed = {'revision':number, 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                            'index_directory_identity':list(index_identity), 'preparation':prepared}

                async def query(session):
                    """Require current source and semantic owners, never interpret a missing match as proof of absence."""
                    read = await session.call_tool('ken_read', {'path':'measurement.py', 'include':['source'], 'start_line':1, 'end_line':6})
                    semantic = await session.call_tool('ken_find', {'query':f'Function returning the captured measurement {value}', 'scope':'symbols', 'piece_kind':'symbol', 'max_chars':6000})
                    for label, response in [('read',read), ('semantic',semantic)]:
                        encoded = response.model_dump_json()
                        (root/(prefix+'-'+label+'.json')).write_text(encoded+'\n')
                        assert not response.isError and symbol in encoded and str(value) in encoded, label+' did not return the current synthetic source'
                        if number == 2:
                            assert 'old_measurement' not in encoded, label+' returned the previous symbol after refresh'
                        observed[label+'_sha256'] = hashlib.sha256(encoded.encode()).hexdigest()

                await visit(trial, installation, args.model_cache, query, operation_key=prefix+'-mcp')
                result['revisions'].append(observed)
                print('Verified revision', number, flush=True)
        result['lifecycle'] = json.loads((trial.root/'lifecycle.json').read_text())
        assert result['lifecycle']['domain_removed'] and result['lifecycle']['all_peers_closed']
        assert len(result['revisions']) == 2 and result['revisions'][0]['source_sha256'] != result['revisions'][1]['source_sha256']
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        if trial is not None and (trial.root/'lifecycle.json').exists():
            result['lifecycle'] = json.loads((trial.root/'lifecycle.json').read_text())
        (root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'status':result['status'], 'model_turns_submitted':0}), flush=True)


if __name__ == '__main__':
    from evals.runtime.kernel_trial import arguments

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--ken-command', type=Path, required=True)
    parser.add_argument('--model-cache', type=Path, required=True)
    parser.add_argument('--memory-mib', type=int, required=True)
    asyncio.run(main(arguments(parser)))
