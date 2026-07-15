"""Typed canonical records produced by official GSTR-2B imports."""
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from models.schemas import ReconLine


@dataclass(frozen=True)
class Gstr2bDocument:
    identity_key: str
    supplier_gstin: str
    invoice_number: str
    invoice_date: date
    document_type: str
    amendment_of_key: str | None
    taxable_paise: int
    igst_paise: int
    cgst_paise: int
    sgst_paise: int
    cess_paise: int
    total_paise: int
    original: dict[str, Any]

    def as_recon_line(self) -> ReconLine:
        section = str(self.original.get("section") or self.document_type).lower()
        legacy_id = f"2b-{section}-{self.supplier_gstin}-{self.invoice_number}".lower()
        return ReconLine(
            id=legacy_id,
            date=self.invoice_date.isoformat(),
            description=self.document_type.replace("_", " ").title(),
            counterparty=self.supplier_gstin,
            amount=self.total_paise,
            ref=self.invoice_number,
            gstin=self.supplier_gstin,
        )


@dataclass(frozen=True)
class Gstr2bParseResult:
    gstin: str
    return_period: str
    parser_version: str
    documents: tuple[Gstr2bDocument, ...]
    source_counts: dict[str, int]
    source_totals: dict[str, int]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def lines(self) -> list[ReconLine]:
        return [document.as_recon_line() for document in self.documents]

    # Compatibility for callers that previously treated the parser result as a list.
    def __len__(self) -> int:
        return len(self.documents)

    def __getitem__(self, index: int) -> ReconLine:
        return self.documents[index].as_recon_line()

    def __iter__(self):
        return iter(self.lines)
