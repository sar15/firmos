"""Base connector protocol. All connectors implement this shape."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ConnectorProtocol(Protocol):
    """Every connector module under connectors/<name>/ exposes this interface."""

    connector_id: str  # e.g. 'zoho_books', 'gstn_gsp'

    async def connect(self, firm_id: str, **kwargs) -> dict:
        """Initiate connection (OAuth redirect URL, credential check, etc.)."""
        ...

    async def disconnect(self, firm_id: str) -> None:
        """Revoke tokens and mark DISCONNECTED."""
        ...

    async def health_check(self, firm_id: str) -> str:
        """Return 'healthy' | 'degraded' | 'error'."""
        ...
