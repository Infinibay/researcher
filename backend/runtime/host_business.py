"""Host-owned business HTTP, without a child process or model-visible credentials."""

import asyncio
import json
from contextlib import asynccontextmanager

from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
    ToolAnnotations,
)
from pydantic import ValidationError

from backend.research.async_http_client import AsyncResearcherHTTPClient
from backend.research.http_client import ResearcherClientError
from backend.runtime.business_definitions import definitions


class HostBusinessPeer:
    """Serve host-selected business tools only while the original attempt authority remains live."""

    def __init__(self, client, *, active, withdraw, names=None):
        """Expose only the business names selected by the trusted attempt controller."""
        self._client, self._active, self._withdraw = client, active, withdraw
        self._definitions = {
            tool.name: tool for tool in definitions(client, names=names)
        }
        self._closing = None
        self.closed = False

    async def list_tools(self):
        """Expose the host-selected schemas only while the original business scope remains admitted."""
        if self._closing is not None or not self._active():
            raise ResearcherClientError("Business admission authority ended")
        return ListToolsResult(
            tools=[
                Tool(
                    name=definition.name,
                    description=definition.description,
                    inputSchema=definition.wire_schema(),
                    annotations=ToolAnnotations(**definition.annotations),
                )
                for definition in self._definitions.values()
            ]
        )

    async def call_tool(self, name, arguments):
        """Validate admitted arguments, invoke the bound handler and recheck live authority before returning its result."""
        try:
            if self._closing is not None or not self._active():
                raise ResearcherClientError("Business admission authority ended")
            definition = self._definitions.get(name)
            if definition is None:
                raise ResearcherClientError("Unknown business tool")
            parsed = definition.arguments.model_validate(arguments)
            result = await definition.handler(
                **{key: getattr(parsed, key) for key in type(parsed).model_fields}
            )
            if self._closing is not None or not self._active():
                raise ResearcherClientError(
                    "Attempt ended while the tool ran; reconcile the original operation_key"
                )
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(result, ensure_ascii=False, allow_nan=False),
                    )
                ]
            )
        except ValidationError:
            message = "Invalid business tool arguments; use the admitted schema"
        except ResearcherClientError as error:
            message = str(error)
        return CallToolResult(
            isError=True, content=[TextContent(type="text", text=message)]
        )

    async def aclose(self):
        """Withdraw server-side authority immediately and join one shared shielded cleanup task."""
        if self._closing is None:
            # Immediate server-side authority withdrawal must precede IO cleanup.
            self._withdraw()
            self._closing = asyncio.create_task(self._shutdown())
        await asyncio.shield(self._closing)

    async def _shutdown(self):
        """Close the owned HTTP client and mark the peer closed only after that cleanup succeeds."""
        await self._client.aclose()
        self.closed = True


@asynccontextmanager
async def host_business(
    *, api_url, token, withdraw, active=lambda: True, transport=None, names=None
):
    """The caller supplies the API's actual live-grant withdrawal, not a receipt.

    This closes local HTTP and withdraws future server effects. A server effect
    already committed is not undone, and an uncertain receipt is never replayed.
    The host must still own/enroll its API actor and persist grant retirement.
    """
    async with AsyncResearcherHTTPClient(api_url, token, transport=transport) as client:
        peer = HostBusinessPeer(client, active=active, withdraw=withdraw, names=names)
        try:
            yield peer
        finally:
            await peer.aclose()
