"""Published-Ken-shaped MCP/prepare peer used only for owned composition tests."""

import json
import os
import sys
from pathlib import Path

root = Path(os.environ["KEN_PROJECT_ROOT"])
if sys.argv[1] == "retrieval":
    print('{"status":"ready"}')
    raise SystemExit(0)
names = ("ken_find", "ken_read", "ken_recall", "ken_related", "ken_remember")
for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    result = {}
    if method == "initialize":
        result = {
            "protocolVersion": request["params"]["protocolVersion"],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "controlled-ken", "version": "1"},
        }
    elif method == "tools/list":
        selected = names[:-1] if (root / ".ken/incomplete").exists() else names
        result = {
            "tools": [
                {
                    "name": name,
                    "inputSchema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                }
                for name in selected
            ]
        }
    elif method == "tools/call":
        result = {
            "content": [
                {
                    "type": "text",
                    "text": (root / request["params"]["arguments"]["path"]).read_text(),
                }
            ],
            "isError": False,
        }
    if "id" in request:
        print(
            json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}),
            flush=True,
        )
