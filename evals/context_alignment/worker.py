"""Serve one synthetic installed runtime with a frozen evaluation policy and identical tool instrumentation."""

import argparse
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path


def bind_policy(policy, registered_task_type, *, execution_kind='research'):
    """Bind frozen bytes to one exact admitted capability; no evaluation can widen a role's authority."""
    allowed = {('research', task) for task in ('investigation', 'research', 'plan', 'review')}
    allowed.update({('development', 'code'), ('code_review', 'code'), ('finding_review', 'research')})
    if (execution_kind, registered_task_type) not in allowed:
        raise ValueError('Unsupported evaluation capability and task type')

    def instructions(kind, task_type, *, checks=(), limits=None):
        """Return exact registered bytes, without adding live policy/budgets, only for the selected profile."""
        if (kind, task_type) != (execution_kind, registered_task_type):
            raise ValueError('Evaluation policy cannot override another capability')
        return policy.decode()

    return instructions


def main():
    """Patch only this isolated evaluation process; preserve the installed host's authority and runtime controls."""
    parser=argparse.ArgumentParser()
    parser.add_argument('--installation',type=Path,required=True)
    parser.add_argument('--policy',type=Path,required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--gate',action='store_true')
    parser.add_argument('--task-type', choices=('investigation', 'research', 'plan', 'review', 'code'), default='investigation')
    parser.add_argument('--execution-kind', choices=('research', 'development', 'code_review', 'finding_review'), default='research')
    args=parser.parse_args()
    policy=args.policy.read_bytes()
    if hashlib.sha256(policy).hexdigest()!=args.sha256:
        raise ValueError('Frozen evaluation policy changed')
    from backend.runtime.host_installation import host_environment
    os.environ.update(host_environment(args.installation))
    from backend.runtime import owned_runtime
    from backend.runtime.business_mediation import ProjectTools
    original=ProjectTools.call
    output=args.installation.parent
    gated=False

    async def record_call(self, params):
        """Record actual mediated results; optionally hold the first completed Ken read for a real owner correction."""
        nonlocal gated
        started=time.monotonic()
        response=await original(self,params)
        record={'tool':params.get('tool'),'arguments':params.get('arguments'),'response':response,
                'seconds':time.monotonic()-started}
        with (output/'tools.jsonl').open('a') as stream:
            stream.write(json.dumps(record,ensure_ascii=False)+'\n')
        if args.gate and params.get('tool')=='ken_read' and response.get('success') is True and not gated:
            gated=True
            (output/'correction-ready').write_text('Original Ken read completed; response held before model delivery.\n')
            async with asyncio.timeout(30):
                while not (output/'correction-release').exists():
                    await asyncio.sleep(.05)
        return response

    owned_runtime.build_instructions=bind_policy(policy, args.task_type, execution_kind=args.execution_kind)
    ProjectTools.call=record_call
    import uvicorn
    from backend.api.main import create_app
    uvicorn.run(create_app(),host='127.0.0.1',port=args.port,log_level='warning',access_log=False)


if __name__=='__main__':
    main()
