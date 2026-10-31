"""Pair a local browser without exposing OAuth or model tool credentials."""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.api.local_access import COOKIE

router = APIRouter(prefix="/api/session", tags=["owner session"])


class PairOwner(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=256)


@router.get("")
async def session_status(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    session = request.state.owner_session
    if session is None:
        return {"authenticated": False}
    return {"authenticated": True, "csrf_token": session.csrf_token}


@router.post("")
async def pair_owner(body: PairOwner, request: Request, response: Response):
    access = request.app.state.local_access
    try:
        token, session = access.pair(body.code)
    except PermissionError as exc:
        raise HTTPException(
            401, str(exc), headers={"Cache-Control": "no-store"}
        ) from exc
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        path="/",
        max_age=int(access.session_seconds),
    )
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True, "csrf_token": session.csrf_token}


@router.delete("", status_code=204)
async def end_session(request: Request, response: Response):
    access = request.app.state.local_access
    session = request.state.owner_session
    if session is not None:
        access.revoke(session)
    response.delete_cookie(
        COOKIE,
        path="/",
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
    )
    response.headers["Cache-Control"] = "no-store"
