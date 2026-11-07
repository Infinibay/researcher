"""HTTP composition and credential translation for the research tool boundary."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.api import config
from backend.research.acquisition import BoundedReferenceReader
from backend.research.context7 import Context7Reader
from backend.research.models import ResearchForbidden, ResearchNotFound, ResearchScope
from backend.research.parser_process import PDFParser
from backend.research.service import ResearchService
from backend.research.sqlite_store import SQLiteResearchStore
from backend.research.spider import SpiderReader
from backend.research.web_fetcher import PublicWebFetcher

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class ResearchContext:
    """Authenticated scope and its repository/acquisition services for one HTTP call."""

    store: SQLiteResearchStore
    scope: ResearchScope
    service: ResearchService


def get_research_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> ResearchContext:
    """Bind tool credentials to data and cancellable workers without model-chosen scope."""
    if credentials is None:
        raise HTTPException(
            401,
            "Host-issued tool credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Kept at the composition edge until legacy DB/config consumers migrate.
    from backend.tools.base.db import get_db_path

    store = getattr(request.app.state, "runtime_research_store", None)
    if store is None:
        store = SQLiteResearchStore(
            get_db_path(), runtime_authority=request.app.state.live_grants.allows
        )
    try:
        scope = store.authorize(credentials.credentials)
    except (ResearchForbidden, ResearchNotFound) as exc:
        raise HTTPException(
            401,
            "Tool credentials expired, revoked or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if {"project_id", "task_id", "agent_id"} & set(request.query_params):
        raise HTTPException(
            422,
            "Project, task and actor are bound to tool credentials; do not supply them in a query",
        )
    from backend.runtime.auxiliary_budget import AuxiliaryBudget

    parser = PDFParser(owner=request.app.state.live_grants, grant_id=scope.grant_id,
                       accounting=AuxiliaryBudget(store.database,scope.project_id,research=store,scope=scope))
    return ResearchContext(
        store,
        scope,
        ResearchService(
            store,
            spider=SpiderReader.from_environment(
                web_policy=request.app.state.web_access_policy,
                owner=request.app.state.live_grants, grant_id=scope.grant_id,
            ),
            context7=Context7Reader.from_environment(
                owner=request.app.state.live_grants, grant_id=scope.grant_id,
            ),
            reference_reader=BoundedReferenceReader(
                Path(config.UPLOAD_DIR),
                pdf_parser=parser,
            ),
            web_fetcher=PublicWebFetcher(
                policy=request.app.state.web_access_policy,
                pdf_parser=parser,
                owner=request.app.state.live_grants,
                grant_id=scope.grant_id,
            ),
        ),
    )


Context = Annotated[ResearchContext, Depends(get_research_context)]
