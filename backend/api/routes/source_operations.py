"""Explicit owner source setup controls: resource preparation is separate from native inference, remote creation and publication."""

import asyncio
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.api.routes.runs import service
from backend.git.source_operations import SourceRequest

router = APIRouter(prefix='/api/projects/{project_id}/source-operations', tags=['sources'])


class PrepareSource(BaseModel):
    """Original owner selection with no shell commands, caller credentials, namespace identities or fabricated task IDs."""

    model_config = ConfigDict(extra='forbid', strict=True)
    operation_key: str = Field(pattern=r'^[A-Za-z0-9_.:-]{1,128}$')
    mode: Literal['create', 'adopt', 'clone', 'create_remote']
    name: str = Field(min_length=1, max_length=81)
    path: str | None = Field(default=None, max_length=4096)
    branch: str | None = Field(default=None, max_length=255)
    remote_url: str | None = Field(default=None, max_length=4096)
    remote_owner: str | None = Field(default=None, max_length=81)
    private: bool | None = None
    use_configured_auth: bool = False
    remote_server: str | None = Field(default=None, max_length=2048)


class StopSource(BaseModel):
    """Exact observed administrative target; a stale browser cannot stop a later reconciliation fence."""

    model_config = ConfigDict(extra='forbid', strict=True)
    operation_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    fence: int = Field(ge=0)


class RepairSource(StopSource):
    """Separate explicit continuation of one observed closed local attempt; no arbitrary commands or invented namespace grants are accepted."""

    repair_key: str = Field(pattern=r'^[A-Za-z0-9_.:-]{1,128}$')


class ReleaseSource(StopSource):
    """Explicit end of an observed closed local reservation; original closure comes from trusted stores, never from the caller."""

    release_key: str = Field(pattern=r'^[A-Za-z0-9_.:-]{1,128}$')


@router.get('')
async def source_options(project_id: int, request: Request):
    """Expose only the configured server and account label for deliberate owner selection, without credentials, host secret paths or network effects."""
    runtime = service(request)
    await asyncio.to_thread(runtime.sources.records.list, project_id)
    transport = runtime.runtime.remote_transport
    return JSONResponse({'remote_server': transport.api_base if transport else None, 'remote_username': transport.username if transport else None}, headers={'Cache-Control':'no-store'})


@router.post('', status_code=202)
async def prepare_source(project_id: int, body: PrepareSource, request: Request):
    """Save and schedule exactly one explicit source operation; native turns, implicit remote creation and force pushes are outside this request."""
    from fastapi import HTTPException

    try:
        intent = SourceRequest(**body.model_dump(exclude={'operation_key'}))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    value = await service(request).sources.submit(project_id, body.operation_key, intent)
    return JSONResponse(value, status_code=202, headers={'Cache-Control':'no-store'})


@router.get('/{operation_key}')
async def source_operation(project_id: int, operation_key: str, request: Request):
    """Observe this exact saved intent and current local handle without fetching remotes, probing Git or choosing a newest operation."""
    value = await asyncio.to_thread(service(request).sources.view, project_id, operation_key)
    return JSONResponse(value, headers={'Cache-Control':'no-store'})


@router.post('/{operation_key}/stop')
async def stop_source(project_id: int, operation_key: str, body: StopSource, request: Request):
    """Withdraw the observed source attempt and drain its actual local owner before acknowledging any verified local closure."""
    value = await service(request).sources.stop(project_id, operation_key, **body.model_dump())
    return JSONResponse(value, headers={'Cache-Control':'no-store'})


@router.post('/{operation_key}/observe', status_code=202)
async def observe_source(project_id: int, operation_key: str, request: Request, body: StopSource | None = None):
    """Reconcile the selected original identity/fence when supplied; retain bodyless compatibility without letting historical controls silently select a different attempt."""
    value = await service(request).sources.reconcile(project_id, operation_key, **(body.model_dump() if body else {}))
    return JSONResponse(value, status_code=202, headers={'Cache-Control':'no-store'})


@router.post('/{operation_key}/repair', status_code=202)
async def repair_source(project_id: int, operation_key: str, body: RepairSource, request: Request):
    """Authorize fixed missing local stages after original closure, preserving existing files and separately recording the repair identity before scheduling."""
    value = await service(request).sources.repair(project_id, operation_key, **body.model_dump())
    return JSONResponse(value, status_code=202, headers={'Cache-Control':'no-store'})


@router.post('/{operation_key}/release')
async def release_source(project_id: int, operation_key: str, body: ReleaseSource, request: Request):
    """Close one original local reservation after verified closure, retaining files/history and requiring a separate request for subsequent adoption."""
    value = await service(request).sources.release(project_id, operation_key, **body.model_dump())
    return JSONResponse(value, headers={'Cache-Control':'no-store'})
