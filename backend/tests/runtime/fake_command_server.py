"""Local subprocess-backed wire peer; deliberately not a sandbox implementation."""

import asyncio
import base64
import json
import os
import sys

jobs = {}
requests = set()


def send(value):
    print(json.dumps(value), flush=True)


async def output(reader, job_id, stream, cap):
    used = 0
    while chunk := await reader.read(128):
        remaining = max(0, cap - used)
        if remaining:
            send(
                {
                    "method": "command/exec/outputDelta",
                    "params": {
                        "processId": job_id,
                        "stream": stream,
                        "deltaBase64": base64.b64encode(chunk[:remaining]).decode(),
                        "capReached": len(chunk) > remaining,
                    },
                }
            )
        elif used == cap:
            send(
                {
                    "method": "command/exec/outputDelta",
                    "params": {
                        "processId": job_id,
                        "stream": stream,
                        "deltaBase64": "",
                        "capReached": True,
                    },
                }
            )
        used += len(chunk)


async def handle(request):
    method, params, ident = (
        request.get("method"),
        request.get("params", {}),
        request.get("id"),
    )
    if method == "initialized":
        return
    if method == "initialize":
        send(
            {
                "id": ident,
                "result": {
                    "serverInfo": {"name": "controlled-command-peer", "version": "0"}
                },
            }
        )
    elif method == "account/read":
        send({"id": ident, "result": {"account": None}})
    elif method == "command/exec":
        assert params["permissionProfile"] == "researcher_jobs"
        assert params["streamStdoutStderr"] is True
        assert params["timeoutMs"] > 0 and params["outputBytesCap"] > 0
        job_id = params["processId"]
        if job_id in jobs:
            send(
                {
                    "id": ident,
                    "error": {"code": -32602, "message": "duplicate process id"},
                }
            )
            return
        process = await asyncio.create_subprocess_exec(
            *params["command"],
            cwd=params["cwd"],
            env={"PATH": os.defpath, "HOME": params["cwd"]},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        jobs[job_id] = process
        streams = [
            asyncio.create_task(
                output(process.stdout, job_id, "stdout", params["outputBytesCap"])
            ),
            asyncio.create_task(
                output(process.stderr, job_id, "stderr", params["outputBytesCap"])
            ),
        ]
        try:
            await asyncio.wait_for(process.wait(), params["timeoutMs"] / 1000)
        except TimeoutError:
            process.kill()
            await process.wait()
        await asyncio.gather(*streams)
        send(
            {
                "id": ident,
                "result": {"exitCode": process.returncode, "stdout": "", "stderr": ""},
            }
        )
    elif method == "command/exec/terminate":
        process = jobs.get(params["processId"])
        if process is None:
            send(
                {
                    "id": ident,
                    "error": {"code": -32602, "message": "unknown process id"},
                }
            )
            return
        if process.returncode is None:
            process.kill()
        send({"id": ident, "result": {}})
    else:
        send({"id": ident, "error": {"code": -32601, "message": "unsupported method"}})


async def main():
    reader = asyncio.StreamReader()
    await asyncio.get_running_loop().connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
    )
    try:
        while line := await reader.readline():
            task = asyncio.create_task(handle(json.loads(line)))
            requests.add(task)
            task.add_done_callback(requests.discard)
    finally:
        for process in jobs.values():
            if process.returncode is None:
                process.kill()
        if requests:
            await asyncio.gather(*requests, return_exceptions=True)


asyncio.run(main())
