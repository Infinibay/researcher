"""Owner-only retained-work history and explicit original-operation quarantine, removal and data recovery."""

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.api.routes.runs import service

router=APIRouter(prefix='/api/projects/{project_id}/retained-work',tags=['retained-work'])


class QuarantineWork(BaseModel):
    """Explicit retention period and acknowledgement that the original copy becomes unavailable for execution/publication."""
    model_config=ConfigDict(extra='forbid',strict=True)
    operation_key:str=Field(pattern=r'^[A-Za-z0-9_.:-]{1,128}$')
    retention_days:int=Field(ge=1,le=3650)
    acknowledge_unavailability:Literal[True]


class RecoverWork(BaseModel):
    """One observed archive revision for removal or new-data recovery; callers cannot select an arbitrary filesystem target."""
    model_config=ConfigDict(extra='forbid',strict=True)
    operation_key:str=Field(pattern=r'^[A-Za-z0-9_.:-]{1,128}$')
    archive_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')


@router.get('')
async def retained_work(project_id:int,request:Request,offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100)):
    """List documentary copy/archive states without starting Git, cleanup or inference."""
    return await asyncio.to_thread(service(request).retention.store.list,project_id,offset=offset,limit=limit)


@router.get('/operations')
async def retention_operations(project_id:int,request:Request,offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100)):
    """Read paged original receipts and pending failures; absence of a response is never treated as absence of an operation."""
    return await asyncio.to_thread(service(request).retention.store.operations,project_id,offset=offset,limit=limit)


@router.get('/operations/{operation_key}')
async def retention_operation(project_id:int,operation_key:str,request:Request):
    """Recover the original owner decision by stable key without repeating its effect."""
    return await asyncio.to_thread(service(request).retention.store.operation,project_id,operation_key)


@router.post('/operations/{operation_key}/reconcile',status_code=202)
async def reconcile_retention(project_id:int,operation_key:str,request:Request):
    """Resume only an explicitly selected pending operation, with its original paths, archive and scope."""
    return await service(request).retention.reconcile(project_id,operation_key)


@router.post('/{attempt_id}/quarantine',status_code=202)
async def quarantine_work(project_id:int,attempt_id:str,body:QuarantineWork,request:Request):
    """Fence new use of one closed private copy and retain its original archive decision before background copying."""
    try:return await service(request).retention.submit(project_id,attempt_id,body.operation_key,'archive',**body.model_dump(exclude={'operation_key'}))
    except ValueError as error:raise HTTPException(422,str(error)) from error


@router.post('/{attempt_id}/{action}',status_code=202)
async def recover_work(project_id:int,attempt_id:str,action:Literal['remove','restore'],body:RecoverWork,request:Request):
    """Apply retention before original-copy removal or recover archived bytes to a fresh destination without reviving old authority."""
    try:return await service(request).retention.submit(project_id,attempt_id,body.operation_key,action,archive_sha256=body.archive_sha256)
    except ValueError as error:raise HTTPException(422,str(error)) from error
