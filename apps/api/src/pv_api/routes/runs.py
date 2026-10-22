"""Runs: what happened during a workflow. Every route is scoped to the signed-in user."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from pv_api.deps import CurrentUser, EngineDep
from pv_api.schemas import RunDetail, RunList
from pv_api.services import run_service

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=RunList)
def list_runs(
    user: CurrentUser,
    engine: EngineDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunList:
    return run_service.list_runs(engine, user.user_id, limit=limit, offset=offset)


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: uuid.UUID, user: CurrentUser, engine: EngineDep) -> RunDetail:
    return run_service.get_run(engine, user.user_id, run_id)
