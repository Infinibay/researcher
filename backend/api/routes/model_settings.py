"""Paired-owner model policy controls, isolated from model-side tool grants, subscription secrets and native execution authority."""

import asyncio

from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field

from backend.api.routes.runs import service
from backend.runtime.model_settings import ModelSettings
from backend.runtime.owned_runtime import OwnedCodexRuntime

router=APIRouter(prefix='/api/model-settings',tags=['configuration'])


class UpdateModelSetting(BaseModel):
    """Replace one exact observed scope revision with a complete model/effort pair or explicit inheritance; credentials and permission fields are forbidden."""
    model_config=ConfigDict(extra='forbid',strict=True)
    project_id:int|None=Field(default=None,ge=1)
    actor_id:str|None=Field(default=None,min_length=1,max_length=128)
    expected_revision:int=Field(ge=0)
    model:str|None=Field(max_length=128)
    reasoning_effort:str|None=Field(max_length=32)


def configured(request):
    """Require the actual owned subscription adapter; legacy adapters and tool tokens cannot become alternate model routers."""
    runtime=service(request)
    if not isinstance(runtime.runtime,OwnedCodexRuntime):raise HTTPException(503,'Configura el runtime de Codex con propiedad de procesos antes de elegir modelos.')
    return runtime


def view(runtime,project_id=None,actor_id=None):
    """Show effective future policy and the last actual native catalog observation, explicitly absent before a catalog has been observed."""
    native=runtime.runtime
    result=ModelSettings(runtime.store).view(project_id,actor_id,host_model=native.model,host_effort=native.reasoning_effort)
    return {**result,'catalog':dict(native._model_catalog) if native._model_catalog else None,'provider':'openai_subscription','applies_to':'new_attempts_only'}


@router.get('')
async def read_settings(request:Request,project_id:int|None=None,actor_id:str|None=None):
    """Read one explicitly selected scope without opening native processes, querying an external account or spending a model turn."""
    try:result=await asyncio.to_thread(view,configured(request),project_id,actor_id)
    except ValueError as error:raise HTTPException(422,str(error)) from error
    return JSONResponse(result,headers={'Cache-Control':'no-store'})


@router.put('')
async def update_settings(body:UpdateModelSetting,request:Request):
    """Save only the owner's chosen revision; a lost response or stale editor cannot silently overwrite a later choice or modify active attempts."""
    runtime=configured(request)
    try:
        await asyncio.to_thread(ModelSettings(runtime.store).update,**body.model_dump())
        result=await asyncio.to_thread(view,runtime,body.project_id,body.actor_id)
    except ValueError as error:raise HTTPException(422,str(error)) from error
    return JSONResponse(result,headers={'Cache-Control':'no-store'})
