"""Actual Textual owner note over localhost HTTP/SQLite with no runtime inference; view and backend share explicit scope without another engine."""

import asyncio
import json
import os
import socket
from pathlib import Path

import uvicorn


async def test_tui_records_explanatory_note_through_actual_owner_service(service_setup, socket_enabled, tmp_path):
    """A visible project/server and real note receipt preserve the correction bridge without activating either native runs or legacy agent events."""
    from textual.widgets import Input, RichLog

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.cli.owner_client import OwnerClient
    from backend.cli.tui import ResearcherTUI
    from backend.orchestrator import ProjectOrchestrator

    code='synthetic-textual-owner-key-at-least-32-characters'
    app=create_app(access=LocalAccess(pairing_key=code))
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
    origin='http://127.0.0.1:'+str(listener.getsockname()[1])
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False))
    serving=asyncio.create_task(server.serve(sockets=[listener]))
    key=tmp_path/'owner.key';key.write_text(code);key.chmod(0o600)
    client=None
    try:
        for _ in range(100):
            if server.started:break
            if serving.done():await serving
            await asyncio.sleep(.05)
        assert server.started
        client=OwnerClient(origin=origin,project_id=101,key_file=key,state_dir=tmp_path/'terminal')
        controller=ProjectOrchestrator(project_id=101,owner_client=client)
        view=ResearcherTUI(controller)
        async with view.run_test(size=(110,36))as pilot:
            assert '101' in str(view.query_one('#scope').render())
            view.query_one('#command',Input).value='Gracias. La nota no autoriza una tarea.'
            await pilot.press('enter')
            for _ in range(100):
                await pilot.pause(.05)
                if service_setup.c.conn.execute('SELECT count(*)FROM chat_messages').fetchone()[0]==1 and len(view.query_one('#output',RichLog).lines)>3:break
            assert service_setup.c.conn.execute('SELECT count(*)FROM chat_messages').fetchone()[0]==1
            assert service_setup.c.conn.execute('SELECT count(*)FROM agent_events').fetchone()[0]==0
            assert service_setup.c.conn.execute('SELECT count(*)FROM runtime_runs').fetchone()[0]==0
            assert client.pending()is None
            await pilot.pause()
            if os.environ.get('RESEARCHER_TERMINAL_QA_DIR'):
                out=Path(os.environ['RESEARCHER_TERMINAL_QA_DIR']);out.mkdir(parents=True,exist_ok=True)
                (out/'owner-console.svg').write_text(view.export_screenshot())
                (out/'evidence.json').write_text(json.dumps({'status':'passed','scope':'Actual Textual/OwnerClient/HTTP/owner session/SQLite, no inference runtime configured','columns':110,'rows':36,'notes':1,'agent_events':0,'native_runs':0,'pending_action':False},indent=2)+'\n')
    finally:
        if client:client.close()
        server.should_exit=True
        await asyncio.wait_for(serving,10)
        listener.close()
