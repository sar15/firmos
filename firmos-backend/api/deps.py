"""Verified identity and transaction-scoped tenant database dependencies."""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, HTTPException, Request

from core.database import Database
from core.security import decode_supabase_jwt


ROLE_PERMISSIONS = {
    "OWNER": frozenset({"connector.manage", "books.read", "books.propose", "books.approve", "books.execute", "compliance.review"}),
    "ADMIN": frozenset({"connector.manage", "books.read", "books.propose", "books.approve", "books.execute", "compliance.review"}),
    "PREPARER": frozenset({"books.read", "books.propose"}),
    "REVIEWER": frozenset({"books.read", "books.approve", "compliance.review"}),
    "VIEWER": frozenset({"books.read"}),
}


class FirmContext:
    __slots__ = ("user_id", "firm_id", "role", "email", "permissions")

    def __init__(self, user_id: str, firm_id: str, role: str, email: str = "",
                 permissions: frozenset[str] | None = None):
        self.user_id, self.firm_id = user_id, firm_id
        self.role, self.email = role.upper(), email
        self.permissions = permissions or ROLE_PERMISSIONS.get(self.role, frozenset())

    def require(self, permission: str) -> None:
        if permission not in self.permissions:
            raise HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED", "permission": permission})


def _bearer(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED"})
    return token


async def get_current_firm(request: Request) -> FirmContext:
    try:
        claims = decode_supabase_jwt(_bearer(request))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"}) from exc
    if Database.pool is None:
        raise HTTPException(status_code=503, detail={"code": "DATABASE_UNAVAILABLE"})
    async with Database.pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT firm_id, role FROM firm_memberships
               WHERE user_id=$1::uuid AND status='ACTIVE' ORDER BY created_at LIMIT 1""",
            claims["sub"],
        )
    if not row:
        raise HTTPException(status_code=403, detail={"code": "FIRM_MEMBERSHIP_REQUIRED"})
    context = FirmContext(claims["sub"], row["firm_id"], row["role"], claims.get("email", ""))
    request.state.user_id, request.state.firm_id, request.state.role = context.user_id, context.firm_id, context.role
    return context


class _BorrowedConnection:
    def __init__(self, conn): self.conn = conn
    async def __aenter__(self): return self.conn
    async def __aexit__(self, *_): return None


class TransactionPool:
    """Compatibility facade: existing routes borrow one request transaction."""
    def __init__(self, conn): self.connection = conn
    def acquire(self): return _BorrowedConnection(self.connection)


async def get_db(request: Request, firm: FirmContext = Depends(get_current_firm)) -> AsyncIterator[TransactionPool]:
    if Database.pool is None:
        raise HTTPException(status_code=503, detail={"code": "DATABASE_UNAVAILABLE"})
    correlation_id = getattr(request.state, "correlation_id", "")
    async with Database.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('request.jwt.claim.sub', $1, true)", firm.user_id)
            await conn.execute("SELECT set_config('request.jwt.claim.firm_id', $1, true)", firm.firm_id)
            await conn.execute("SELECT set_config('request.jwt.claim.role', $1, true)", firm.role)
            await conn.execute("SELECT set_config('firmos.correlation_id', $1, true)", correlation_id)
            yield TransactionPool(conn)


async def get_conn(db: TransactionPool = Depends(get_db)):
    yield db.connection
