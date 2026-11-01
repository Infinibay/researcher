#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["fastmcp==4.1.4", "httpx==0.28.1", "pydantic==2.14.2"]
# ///
"""Scoped business tools for native agent runtimes; no model or DB client here.

The host provides RESEARCHER_API_URL and RESEARCHER_TOOL_TOKEN. Credentials,
project/task/actor authority, grant issuance and SQL are never tool arguments.
Run in its locked script environment to avoid the legacy MCP dependency clash.
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.research.async_http_client import AsyncResearcherHTTPClient
from backend.research.http_client import ResearcherClientError
from backend.runtime.business_definitions import INSTRUCTIONS, definitions


class _RequestPort:
    def __init__(self):
        self.client = None

    async def request(self, method, path, *, body=None, query=None):
        try:
            if self.client is None:
                self.client = await AsyncResearcherHTTPClient(
                    os.environ.get("RESEARCHER_API_URL", "http://127.0.0.1:8000"),
                    os.environ.get("RESEARCHER_TOOL_TOKEN", ""),
                ).__aenter__()
            return await self.client.request(method, path, body=body, query=query)
        except ResearcherClientError as error:
            raise ToolError(str(error)) from None


port = _RequestPort()


@asynccontextmanager
async def lifespan(server):
    try:
        yield {}
    finally:
        if port.client is not None:
            await port.client.aclose()


mcp = FastMCP("researcher", instructions=INSTRUCTIONS, lifespan=lifespan)
for definition in definitions(port):
    mcp.tool(annotations=definition.annotations)(definition.handler)

if __name__ == "__main__":
    mcp.run(transport="stdio")
