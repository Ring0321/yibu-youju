"""Separate authenticated G0 API. Not imported by app.main or exposed by Compose."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.api.deps import get_current_active_superuser
from app.api.routes import login
from g0.database import database_url
from g0.service import ConflictError, read_run, submit

database_url()
app = FastAPI(title="Yibu G0 infrastructure probe", docs_url=None, redoc_url=None)
app.include_router(login.router, prefix="/api/v1")
admin_only = [Depends(get_current_active_superuser)]


class StartBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: UUID
    prompt: Annotated[str, Field(min_length=1, max_length=200)]


class ResumeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: UUID
    acknowledged: StrictBool


def dispatch(run_id: UUID, command_id: UUID, kind: str, payload: dict) -> dict:
    try:
        return submit(run_id, command_id, kind, payload)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.get("/health")
def health() -> bool:
    return True


@app.post("/g0/runs/{run_id}/start", status_code=202, dependencies=admin_only)
def start(run_id: UUID, body: StartBody) -> dict:
    return dispatch(run_id, body.command_id, "start", {"prompt": body.prompt})


@app.post("/g0/runs/{run_id}/resume", status_code=202, dependencies=admin_only)
def resume(run_id: UUID, body: ResumeBody) -> dict:
    return dispatch(
        run_id, body.command_id, "resume", {"acknowledged": body.acknowledged}
    )


@app.get("/g0/runs/{run_id}", dependencies=admin_only)
def status(run_id: UUID) -> dict:
    try:
        return read_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None
