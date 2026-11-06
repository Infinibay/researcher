"""The public MCP gateway exposes existing scoped business capabilities without legacy SQL, environment identity, provider calls or owner authority."""

import pytest


class RecordingPort:
    """A controlled HTTP port records exact paths/bodies, not an authorization or physical execution witness."""

    def __init__(self):
        """Start an empty effect log and an optional deterministic failure."""
        self.calls = []
        self.failure = None
        self.closed = False

    async def request(self, method, path, *, body=None, query=None):
        """Record one original request without retrying or fabricating a server receipt."""
        self.calls.append((method,path,body,query))
        if self.failure:
            raise self.failure
        return {'source_id':137,'receipt':'original'}

    async def aclose(self):
        """Make retirement of the original HTTP resource observable."""
        self.closed = True


async def test_native_gateway_uses_shared_research_catalogue_and_rejects_forged_scope():
    """Model-supplied task/project/actor/SQL fields cannot choose a different authority or call the HTTP port."""
    from backend.research.stdio_server import BusinessGateway
    from backend.runtime.business_mediation import RESEARCH_NAMES

    port = RecordingPort()
    gateway = BusinessGateway(port)
    assert {tool.name for tool in gateway.tools()} == set(RESEARCH_NAMES)
    assert not {'query_database','task_approve','create_pr','chat_send'} & {tool.name for tool in gateway.tools()}
    invalid = await gateway.call('researcher_capture_web',{'url':'https://example.org','operation_key':'original','project_id':202})
    assert invalid.isError and not port.calls
    unknown = await gateway.call('query_database',{'sql_query':'SELECT * FROM projects'})
    assert unknown.isError and not port.calls


async def test_native_gateway_reuses_the_existing_wire_adapter_without_retry():
    """A failed or lost response may follow an effect; the adapter returns uncertainty and keeps the original request key."""
    from backend.research.http_client import ResearcherClientError
    from backend.research.stdio_server import BusinessGateway

    port = RecordingPort()
    gateway = BusinessGateway(port)
    port.failure = ResearcherClientError('Synthetic uncertain response')
    result = await gateway.call('researcher_capture_web',{'url':'https://example.org','operation_key':'keep-original'})
    assert result.isError and len(port.calls)==1
    assert port.calls[0][2]['operation_key']=='keep-original'
    assert 'retry' in result.content[0].text.lower() or 'original' in result.content[0].text.lower()


def test_native_mcp_configuration_requires_host_token_and_ignores_legacy_identity(monkeypatch):
    """Old project/agent environment variables and an API key cannot mint a scoped business grant."""
    from backend.research.stdio_server import configuration

    monkeypatch.delenv('RESEARCHER_TOOL_TOKEN',raising=False)
    monkeypatch.setenv('INFINIBAY_PROJECT_ID','202')
    monkeypatch.setenv('INFINIBAY_AGENT_ID','assumed-owner')
    monkeypatch.setenv('INFINIBAY_LLM_API_KEY','synthetic-not-a-grant')
    with pytest.raises(ValueError,match='RESEARCHER_TOOL_TOKEN'):
        configuration()


async def test_nested_question_dto_reaches_existing_http_adapter_with_original_key():
    """SDK replacement must preserve typed nested questions and their concrete correction example, not turn DTOs into unusable dictionaries."""
    from backend.research.stdio_server import BusinessGateway

    port = RecordingPort()
    result = await BusinessGateway(port).call('researcher_ask_user',{
        'operation_key':'question-original',
        'questions':[{'id':'source','question':'Which source should guide this task?','example':'The old plan says137; the current request mentions200.'}],
    })
    assert isinstance(result,dict) and len(port.calls)==1
    body = port.calls[0][2]
    assert body['operation_key']=='question-original'
    assert body['questions'][0]['id']=='source'
    assert body['questions'][0]['example']=='The old plan says137; the current request mentions200.'


async def test_standard_sdk_protocol_lists_and_calls_shared_business_tools():
    """Actual MCP initialization/list/call round-trips use the native definitions and safe errors without FastMCP."""
    import anyio
    from mcp import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    from backend.research.stdio_server import BusinessGateway, create_server

    port = RecordingPort()
    server = create_server(BusinessGateway(port))
    async with create_client_server_memory_streams() as (client_streams,server_streams):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(server.run,*server_streams,server.create_initialization_options())
            async with ClientSession(*client_streams) as client:
                initialized = await client.initialize()
                assert initialized.serverInfo.name=='researcher'
                tools = await client.list_tools()
                assert 'researcher_capture_web' in {tool.name for tool in tools.tools}
                success = await client.call_tool('researcher_capture_web',{'url':'https://example.org','operation_key':'protocol-original'})
                assert not success.isError and success.structuredContent['source_id']==137
                rejected = await client.call_tool('query_database',{'sql_query':'SELECT * FROM projects'})
                assert rejected.isError and len(port.calls)==1
            tasks.cancel_scope.cancel()


async def test_unexpected_gateway_error_does_not_echo_internal_credentials_or_request():
    """An uncertain internal failure cannot turn a token or private argument in exception text into protocol output."""
    from backend.research.stdio_server import BusinessGateway

    port = RecordingPort()
    port.failure = RuntimeError('synthetic-secret-must-not-appear')
    result = await BusinessGateway(port).call('researcher_capture_web',{'url':'https://example.org','operation_key':'uncertain-original'})
    assert result.isError and len(port.calls)==1
    assert 'synthetic-secret-must-not-appear' not in result.content[0].text


def test_mcp_help_and_missing_token_leave_storage_and_legacy_identity_unused(monkeypatch,capsys):
    """The installed command never accepts old actor variables as authorization or prints credentials on a refused start."""
    from backend.research.stdio_server import main

    monkeypatch.delenv('RESEARCHER_TOOL_TOKEN',raising=False)
    with pytest.raises(SystemExit) as help_exit:
        main(['--help'])
    assert help_exit.value.code==0
    capsys.readouterr()
    assert main([])==2
    captured=capsys.readouterr()
    assert not captured.out and 'RESEARCHER_TOOL_TOKEN' in captured.err


async def test_actual_stdio_process_serves_protocol_without_storage_or_legacy_authority(tmp_path):
    """A separate Python process initializes/lists/rejects over real stdio; disconnected loopback credentials are syntax only and create no DB or authority."""
    import sys

    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    database = tmp_path / "must-not-exist.sqlite"
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.research.stdio_server"],
        env={
            "RESEARCHER_TOOL_TOKEN": "synthetic-not-an-issued-grant",
            "RESEARCHER_API_URL": "http://127.0.0.1:9",
            "INFINIBAY_DB": str(database),
            "INFINIBAY_PROJECT_ID": "202",
            "INFINIBAY_AGENT_ID": "not-owner-authority",
        },
    )
    with anyio.fail_after(15):
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as client:
                assert (await client.initialize()).serverInfo.name == "researcher"
                assert (await client.list_tools()).tools
                rejected = await client.call_tool("researcher_reference_list", {"project_id": 202})
                assert rejected.isError
                unknown = await client.call_tool("query_database", {"sql_query": "SELECT 1"})
                assert unknown.isError
    assert not database.exists()
