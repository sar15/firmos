"""GstFilingProvider — the protocol that every GSP adapter implements.

Provider-agnostic. Sandbox / WhiteBooks / MasterGST is a config swap.
"""

from typing import Protocol, runtime_checkable

from connectors.gst_filing.types import (
    GstinDetails,
    Gstr2bData,
    ReconReport,
    PurchaseRow,
)


class ManualFilingRequiredError(RuntimeError):
    """V1 prepares return evidence; the CA files it on the government portal."""


@runtime_checkable
class GstFilingProvider(Protocol):
    """Every GSP connector implements this shape."""

    async def verify_gstin(self, gstin: str) -> GstinDetails:
        """Verify a GSTIN and return taxpayer details."""
        ...

    async def fetch_2b(self, gstin: str, period: str) -> Gstr2bData:
        """Fetch GSTR-2B for a return period (MMYYYY)."""
        ...

    async def reconcile_2b(
        self,
        gstin: str,
        period: str,
        purchase_ledger: list[PurchaseRow],
    ) -> ReconReport:
        """Reconcile GSTR-2B against the purchase register.

        Some GSPs (Sandbox) do this as an async job (submit → poll).
        Others do it synchronously. The caller doesn't care.
        """
        ...
