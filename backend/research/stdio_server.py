"""Scoped native business MCP over the standard SDK; host tokens and existing API rules own authority, never ambient project IDs or model-supplied credentials."""

import argparse
import asyncio
import os
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations
from pydantic import ValidationError

from backend.research.async_http_client import AsyncResearcherHTTPClient
from backend.research.http_client import ResearcherClientError, ResearcherEndpoint
from backend.runtime.business_definitions import INSTRUCTIONS, definitions


class BusinessGateway:
    """Adapt the existing research catalogue and typed HTTP handlers without issuing grants, reading storage, choosing actors or retrying effects."""

    def __init__(self, client):
        """Keep one original request port and the same definitions used by the admitted native runtime."""
        self.client = client
        self._definitions = {item.name: item for item in definitions(client)}

    def tools(self) -> list[Tool]:
        """Expose real argument schemas; tool availability is not proof that the host currently authorizes a call."""
        return [
            Tool(name=item.name, description=item.description, inputSchema=item.wire_schema(), annotations=ToolAnnotations(**item.annotations))
            for item in self._definitions.values()
        ]

    @staticmethod
    def _error(message: str) -> CallToolResult:
        """Report a failed/unknown outcome without printing credential, argument or traceback content."""
        return CallToolResult(isError=True, content=[TextContent(type='text', text=message)])

    async def call(self, name: str, arguments: dict) -> CallToolResult | dict:
        """Validate before HTTP, preserve nested DTOs and the original operation key, and leave authorization/fencing to the actual API."""
        definition = self._definitions.get(name)
        if definition is None:
            return self._error('Unknown native business tool. SQL, role activation and owner approval are not available through this gateway.')
        try:
            validated = definition.arguments.model_validate(arguments)
        except ValidationError:
            return self._error('Invalid business tool arguments. Use its declared schema; project, actor and grant authority come from the host.')
        try:
            return await definition.handler(**{key: getattr(validated, key) for key in type(validated).model_fields})
        except ResearcherClientError as error:
            return self._error(str(error) + ' Keep the original operation_key and inspect the saved receipt before retrying; no request was retried here.')
        except Exception:
            return self._error('Business response failed or its outcome is unknown. Inspect the owner workspace and keep the original operation_key; no request was retried here.')


def configuration(environ=None) -> tuple[str, str]:
    """Validate only host-supplied endpoint/token syntax; old environment labels cannot create a grant and syntax does not prove a live grant."""
    environ = os.environ if environ is None else environ
    token = environ.get('RESEARCHER_TOOL_TOKEN', '')
    if not token:
        raise ValueError('RESEARCHER_TOOL_TOKEN must be supplied by the admitting host')
    origin = environ.get('RESEARCHER_API_URL', 'http://127.0.0.1:8000')
    ResearcherEndpoint(origin, token)
    return origin, token


def create_server(gateway: BusinessGateway) -> Server:
    """Build the standard MCP protocol adapter without opening a connection, database or model."""
    server = Server('researcher', instructions=INSTRUCTIONS + '\nThe host validates every grant and context. Configure the required Ken MCP separately through the admitting host. This gateway cannot approve, publish or activate agents.')

    @server.list_tools()
    async def list_tools():
        """Return the shared native research schemas without legacy SQL or owner-only operations."""
        return gateway.tools()

    @server.call_tool(validate_input=False)
    async def call_tool(name, arguments):
        """Use safe typed validation rather than echoing arbitrary input in SDK validation errors."""
        return await gateway.call(name, arguments)

    return server


async def serve(origin: str, token: str) -> None:
    """Own one HTTP client for the actual stdio session and drain it on disconnect/cancellation without reopening or replaying effects."""
    async with AsyncResearcherHTTPClient(origin, token) as client:
        server = create_server(BusinessGateway(client))
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())


def main(argv=None) -> int:
    """Show help without IO, or serve only with an explicit host token; credentials and scope never become command-line/tool arguments."""
    parser = argparse.ArgumentParser(description='Native scoped research MCP. Host supplies RESEARCHER_API_URL and RESEARCHER_TOOL_TOKEN; configure Ken separately. No SQL or grant issuance.')
    parser.parse_args(argv)
    try:
        origin, token = configuration()
    except (ValueError, ResearcherClientError) as error:
        print(f'Native MCP configuration refused: {error}', file=sys.stderr)
        return 2
    try:
        asyncio.run(serve(origin, token))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
