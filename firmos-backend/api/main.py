"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import os
import uuid

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings, settings
from core.logging import setup_logging
from core.redaction import redact_sentry_event
from core.security import StoredCredentialError
from core.errors import AppError, ErrorEnvelope


from core.database import Database


class SettingsCORSMiddleware(CORSMiddleware):
    """Read CORS origins after settings are validated, not at module import."""

    def is_allowed_origin(self, origin: str) -> bool:
        allowed = {value.strip() for value in get_settings().allowed_origins.split(",")}
        return origin in allowed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    setup_logging()

    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1,
            before_send=redact_sentry_event,
        )

    await Database.connect()

    try:
        yield  # app runs here
    finally:
        from connectors.zoho_books.client import close_http_client

        await close_http_client()
        await Database.close()


app = FastAPI(
    title="firmOS API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def correlation_context(request: Request, call_next):
    value = request.headers.get("x-correlation-id", "")
    try:
        correlation_id = str(uuid.UUID(value)) if value else str(uuid.uuid4())
    except ValueError:
        correlation_id = str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    try:
        response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()


@app.exception_handler(AppError)
async def typed_error(request: Request, exc: AppError):
    envelope = ErrorEnvelope(
        exc.code,
        exc.safe_message,
        request.state.correlation_id,
        exc.retryable,
        exc.user_action,
        exc.details,
    )
    return JSONResponse(
        status_code=exc.status_code, content={"error": envelope.asdict()}
    )


@app.exception_handler(StoredCredentialError)
async def stored_credential_error(_request: Request, _exc: StoredCredentialError):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Stored connector credentials are unavailable. Reconnect the connector and try again."
        },
    )


app.add_middleware(
    SettingsCORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    commit = (
        os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT_SHA") or "unknown"
    )
    return {"status": "ok", "commit": commit[:12]}


from api.routes import (
    agent_bank_tools,
    agent_tools,
    audit,
    bank_reconciliation,
    bank_statements,
    capabilities,
    chat,
    classify,
    client_mutations,
    clients,
    compute,
    firms,
    connector_disconnect,
    connector_operations,
    connectors,
    decisions,
    document_list,
    document_review,
    documents,
    gst_rules,
    gst_workpapers,
    gstr2b_runs,
    itr_computation,
    itr_rules,
    itr_workspaces,
    notifications,
    readiness,
    reconciliation,
    registers,
    stream,
    tally_agent,
    tally_bridge_actions,
    tally_routes,
    workflows,
    zoho,
)

app.include_router(clients.router)
app.include_router(client_mutations.router)
app.include_router(connectors.router)
app.include_router(connector_disconnect.router)
app.include_router(documents.router)
app.include_router(document_list.router)
app.include_router(document_review.router)
app.include_router(decisions.router)
app.include_router(reconciliation.router)
app.include_router(gstr2b_runs.router)
app.include_router(gst_workpapers.router)
app.include_router(gst_rules.router)
app.include_router(itr_workspaces.router)
app.include_router(itr_rules.router)
app.include_router(itr_computation.router)
app.include_router(notifications.router)
app.include_router(workflows.router)
app.include_router(audit.router)
app.include_router(compute.router)
app.include_router(firms.router)
app.include_router(zoho.router)
app.include_router(bank_statements.router)
app.include_router(bank_reconciliation.router)
app.include_router(classify.router)
app.include_router(stream.router)
app.include_router(chat.router)
app.include_router(registers.router)
app.include_router(tally_routes.router)
app.include_router(tally_bridge_actions.router)
app.include_router(tally_agent.router)
app.include_router(agent_tools.router)
app.include_router(agent_bank_tools.router)
app.include_router(readiness.router)
app.include_router(readiness.deployment_router)
app.include_router(capabilities.router)
app.include_router(connector_operations.router)
