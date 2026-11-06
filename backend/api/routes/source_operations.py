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


class StopSource(BaseModel):
    """Exact observed administrative target; a stale browser cannot stop a later reconciliation fence."""

    model_config = ConfigDict(extra='forbid', strict=True)
    operation_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    fence: int = Field(ge=0)


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
async def observe_source(project_id: int, operation_key: str, request: Request):
    """Request readonly reconciliation of the original retained directory and closure; an uncertain effect is never blindly reissued."""
    value = await service(request).sources.reconcile(project_id, operation_key)
    return JSONResponse(value, status_code=202, headers={'Cache-Control':'no-store'})
