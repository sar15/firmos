"""AccountingConnector & AccountingPlugin protocol — capability-declared interface.

# ponytail: Small plugin runtime instead of a rigid 14-method god interface.
Each plugin declares typed operations it genuinely supports:
- zoho.read.bills
- zoho.write.bill.create
- tally.read.vouchers
- tally.write.purchase_voucher.create
"""
from typing import Protocol, runtime_checkable, Any, Dict, List
from dataclasses import dataclass
from connectors.gst_filing.types import PurchaseRow, SalesRow


@dataclass(frozen=True)
class LedgerRow:
    """Canonical ledger account representation across Zoho/Tally."""
    id: str
    name: str
    code: str = ""
    group: str = ""


@runtime_checkable
class AccountingPlugin(Protocol):
    """Capability-declared plugin runtime interface."""

    async def capabilities(self) -> List[str]:
        """Return declared operations supported by this plugin, e.g. ['zoho.read.bills', 'zoho.write.bill.create']."""
        ...

    async def read(self, operation: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a typed read operation."""
        ...

    async def execute(self, operation: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a typed write/mutation operation."""
        ...

    async def health(self) -> Dict[str, Any]:
        """Return health status check."""
        ...


@runtime_checkable
class AccountingConnector(Protocol):
    """Legacy compatibility interface for existing adapters."""

    async def capabilities(self) -> list[str]:
        ...

    async def get_ledgers(self) -> list[LedgerRow]:
        ...

    async def create_purchase_bill(self, bill_payload: dict) -> str:
        ...

    async def post_voucher(self, voucher_payload: dict) -> str:
        ...

    async def get_sales_register(self, start_date: str, end_date: str) -> list[SalesRow]:
        ...

    async def get_purchase_register(self, start_date: str, end_date: str) -> list[PurchaseRow]:
        ...

    async def health(self) -> dict:
        ...
