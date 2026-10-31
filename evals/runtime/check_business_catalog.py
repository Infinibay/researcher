"""Verify the real locked MCP catalog; no HTTP effects or generative calls."""

import asyncio
import json
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def main():
    from backend.runtime.business_mediation import BusinessTools, business_peer

    with TemporaryDirectory(prefix="researcher-catalog-") as temporary:
        async with business_peer(
            api_url="http://127.0.0.1:1",
            token="no-authority-schema-check",
            script=REPO / "scripts/researcher_mcp_server.py",
            uv=Path(shutil.which("uv")),
            cache=Path.home() / ".cache/uv",
            home=Path(temporary) / "business",
        ) as peer:
            tools = await BusinessTools.connect(peer)
            schemas = {tool["name"]: tool["inputSchema"] for tool in tools.catalog}
            assert schemas["researcher_finding_record"]["properties"][
                "finding_type"
            ].get("enum") == [
                "observation",
                "hypothesis",
                "experiment",
                "proof",
                "conclusion",
            ]
            assert schemas["researcher_report_write"]["properties"]["report_type"].get(
                "enum"
            ) == ["research", "analysis", "summary"]
            print(
                json.dumps(
                    {
                        "status": "passed",
                        "catalog_hash": tools.catalog_hash,
                        "model_turns_submitted": 0,
                        "tool_count": len(tools.catalog),
                    }
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
