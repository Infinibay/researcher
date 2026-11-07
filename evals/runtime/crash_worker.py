"""Hold one real committed effect at the reply boundary for an owned service-crash trial.

Only this disposable worker is instrumented. Model policy, storage transactions,
native processes and recovery are the installed product's implementations.
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path


def main():
    """Start the installed API with one bounded, observable fault-injection gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--gate', choices=('effect', 'question'), required=True)
    args = parser.parse_args()
    from backend.runtime.host_installation import host_environment

    os.environ.update(host_environment(args.installation))
    from backend.runtime.business_mediation import ProjectTools
    from backend.runtime.service import RuntimeService

    output = args.installation.parent
    call = ProjectTools.call
    question_requested = RuntimeService.question_requested
    gated = False

    def ready(value):
        """Publish readiness atomically only after the real storage operation returned."""
        nonlocal gated
        if gated:
            raise RuntimeError('The crash gate must be reached only once')
        gated = True
        temporary = output / 'gate-ready.tmp'
        temporary.write_text(json.dumps(value) + '\n')
        temporary.replace(output / 'gate-ready.json')

    async def record_call(self, params):
        """Record actual mediated calls and hold a successful capture before model delivery."""
        response = await call(self, params)
        with (output / 'tools.jsonl').open('a') as stream:
            stream.write(json.dumps({'tool': params.get('tool'), 'arguments': params.get('arguments'),
                                     'response': response}, ensure_ascii=False) + '\n')
        if (args.gate == 'effect' and params.get('tool') == 'researcher_capture_reference'
                and response.get('success') is True and not gated):
            ready({'boundary': 'committed_capture_before_reply', 'response': response})
            await asyncio.sleep(60)
            raise TimeoutError('Original supervisor did not kill this gated trial')
        return response

    def hold_question(self, run_id, attempt_id):
        """Freeze the callback after the question commit and before volatile peer withdrawal."""
        if args.gate == 'question' and not gated:
            ready({'boundary': 'committed_question_before_callback', 'run_id': run_id,
                   'attempt_id': attempt_id})
            time.sleep(60)
            raise TimeoutError('Original supervisor did not kill this gated trial')
        return question_requested(self, run_id, attempt_id)

    ProjectTools.call = record_call
    RuntimeService.question_requested = hold_question
    import uvicorn
    from backend.api.main import create_app

    uvicorn.run(create_app(), host='127.0.0.1', port=args.port,
                log_level='warning', access_log=False)


if __name__ == '__main__':
    main()
