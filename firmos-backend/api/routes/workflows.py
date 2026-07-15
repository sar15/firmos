from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from langgraph.types import Command
from pydantic import BaseModel, Field

from api.deps import get_current_firm, FirmContext, get_db
from workflows.graphs import (
    build_t1_workflow,
    build_t2_workflow,
    build_t3_workflow,
    build_t4_workflow,
    get_checkpointer,
)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _graph(workflow_id: str):
    builders = {
        "t1": build_t1_workflow,
        "t2": build_t2_workflow,
        "t3": build_t3_workflow,
        "t4": build_t4_workflow,
    }
    if workflow_id == "t5":
        from workflows.graphs import build_t5_workflow

        return build_t5_workflow()
    builder = builders.get(workflow_id)
    if not builder:
        raise HTTPException(status_code=404, detail="Unknown workflow ID")
    return builder()


def _require_workflow_permission(workflow_id: str, firm: FirmContext) -> None:
    firm.require(
        "compliance.review" if workflow_id in {"t4", "t5"} else "books.propose"
    )


async def _claim_run(
    db_pool: Any,
    workflow_id: str,
    thread_id: str,
    firm: FirmContext,
    client_id: str | None,
) -> str:
    storage_thread_id = f"{firm.firm_id}:{firm.user_id}:{thread_id}"
    async with db_pool.acquire() as conn:
        if client_id:
            exists = await conn.fetchval(
                "SELECT 1 FROM clients WHERE id=$1 AND firm_id=$2",
                client_id,
                firm.firm_id,
            )
            if not exists:
                raise HTTPException(status_code=404, detail="Client was not found")
        await conn.execute(
            """INSERT INTO workflow_runs
               (firm_id,created_by,workflow_id,thread_id,storage_thread_id,client_id)
               VALUES($1,$2::uuid,$3,$4,$5,$6) ON CONFLICT(firm_id,thread_id) DO NOTHING""",
            firm.firm_id,
            firm.user_id,
            workflow_id,
            thread_id,
            storage_thread_id,
            client_id,
        )
    return await _owned_thread(db_pool, workflow_id, thread_id, firm)


async def _owned_thread(
    db_pool: Any, workflow_id: str, thread_id: str, firm: FirmContext
) -> str:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT storage_thread_id FROM workflow_runs
               WHERE firm_id=$1 AND created_by=$2::uuid AND workflow_id=$3 AND thread_id=$4""",
            firm.firm_id,
            firm.user_id,
            workflow_id,
            thread_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Workflow run was not found")
    return row["storage_thread_id"]


async def _invoke(graph, checkpointer, config: dict, value):
    if hasattr(checkpointer, "__aenter__"):
        async with checkpointer as checkpoint:
            await checkpoint.setup()
            return await graph.compile(checkpointer=checkpoint).ainvoke(
                value, config=config
            )
    return await graph.compile(checkpointer=checkpointer).ainvoke(value, config=config)


@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    thread_id: str = Query(min_length=8, max_length=255),
    initial_state: dict | None = None,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Start an owned workflow; user-supplied thread IDs never reach storage."""
    _require_workflow_permission(workflow_id, firm)
    state = dict(initial_state or {})
    state["firm_id"] = firm.firm_id
    client_id = state.get("client_id")
    storage_thread_id = await _claim_run(
        db_pool, workflow_id, thread_id, firm, client_id
    )
    graph = _graph(workflow_id)
    checkpointer = await get_checkpointer(db_pool)
    config = {"configurable": {"thread_id": storage_thread_id}}
    result = await _invoke(graph, checkpointer, config, state)
    return {"ok": True, "state": result}


class ResumeRequest(BaseModel):
    thread_id: str = Field(min_length=8, max_length=255)
    approval_data: dict


@router.post("/{workflow_id}/resume")
async def resume_workflow(
    workflow_id: str,
    req: ResumeRequest,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Resume only the caller's persistent workflow run."""
    _require_workflow_permission(workflow_id, firm)
    storage_thread_id = await _owned_thread(db_pool, workflow_id, req.thread_id, firm)
    graph = _graph(workflow_id)
    checkpointer = await get_checkpointer(db_pool)
    config = {"configurable": {"thread_id": storage_thread_id}}
    result = await _invoke(
        graph, checkpointer, config, Command(resume=req.approval_data)
    )
    return {"ok": True, "state": result}


@router.get("/{workflow_id}/run/{thread_id}")
async def get_workflow_state(
    workflow_id: str,
    thread_id: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool=Depends(get_db),
):
    """Read only the caller's persistent workflow run."""
    _require_workflow_permission(workflow_id, firm)
    storage_thread_id = await _owned_thread(db_pool, workflow_id, thread_id, firm)
    graph = _graph(workflow_id)
    checkpointer = await get_checkpointer(db_pool)
    config = {"configurable": {"thread_id": storage_thread_id}}

    if hasattr(checkpointer, "__aenter__"):
        async with checkpointer as chk:
            await chk.setup()
            app = graph.compile(checkpointer=chk)
            state_snapshot = await app.aget_state(config)
    else:
        app = graph.compile(checkpointer=checkpointer)
        state_snapshot = await app.aget_state(config)

    return {
        "ok": True,
        "state": state_snapshot.values if state_snapshot else None,
        "next": state_snapshot.next if state_snapshot else [],
        "created_at": state_snapshot.created_at if state_snapshot else None,
    }
