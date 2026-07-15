"""Typed validation models for Zoho Books plugin operations.

# ponytail: Strict validation model using integer paise and explicit strings to prevent float rounding errors.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from decimal import Decimal


@dataclass
class ZohoBillItemInput:
    account_id: str
    rate_paise: int  # e.g. 10000 paise = 100.00 INR
    quantity: int = 1
    description: str = ""
    tax_id: Optional[str] = None

    def to_zoho_dict(self) -> Dict[str, Any]:
        rate_dec = (Decimal(self.rate_paise) / Decimal(100)).quantize(Decimal("0.01"))
        d: Dict[str, Any] = {
            "account_id": self.account_id,
            "rate": str(rate_dec),
            "quantity": self.quantity,
        }
        if self.description:
            d["description"] = self.description
        if self.tax_id:
            d["tax_id"] = self.tax_id
        return d


@dataclass
class ZohoBillCreate:
    vendor_id: str
    bill_number: str
    date: str
    line_items: List[ZohoBillItemInput]
    currency_code: str = "INR"
    due_date: Optional[str] = None
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ZohoBillCreate":
        if not payload.get("vendor_id"):
            raise ValueError("ZohoBillCreate requires valid 'vendor_id'")
        if not payload.get("bill_number"):
            raise ValueError("ZohoBillCreate requires 'bill_number'")
        if not payload.get("date"):
            raise ValueError("ZohoBillCreate requires 'date' (YYYY-MM-DD)")
        items_data = payload.get("line_items", [])
        if not items_data:
            raise ValueError("ZohoBillCreate requires at least one item in 'line_items'")

        line_items = []
        for item in items_data:
            line_items.append(
                ZohoBillItemInput(
                    account_id=str(item["account_id"]),
                    rate_paise=int(item["rate_paise"]),
                    quantity=int(item.get("quantity", 1)),
                    description=item.get("description", ""),
                    tax_id=item.get("tax_id"),
                )
            )

        return cls(
            vendor_id=str(payload["vendor_id"]),
            bill_number=str(payload["bill_number"]),
            date=str(payload["date"]),
            line_items=line_items,
            currency_code=payload.get("currency_code", "INR"),
            due_date=payload.get("due_date"),
            notes=payload.get("notes", ""),
        )

    def to_zoho_json(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "vendor_id": self.vendor_id,
            "bill_number": self.bill_number,
            "date": self.date,
            "currency_code": self.currency_code,
            "line_items": [i.to_zoho_dict() for i in self.line_items],
        }
        if self.due_date:
            d["due_date"] = self.due_date
        if self.notes:
            d["notes"] = self.notes
        return d


@dataclass
class ZohoInvoiceItemInput:
    """Invoice lines use existing Zoho items; a chart-of-account ID is not valid here."""
    item_id: str
    rate_paise: int
    quantity: int = 1
    description: str = ""
    tax_id: Optional[str] = None

    def to_zoho_dict(self) -> Dict[str, Any]:
        rate = (Decimal(self.rate_paise) / Decimal(100)).quantize(Decimal("0.01"))
        data: Dict[str, Any] = {"item_id": self.item_id, "rate": str(rate), "quantity": self.quantity}
        if self.description:
            data["description"] = self.description
        if self.tax_id:
            data["tax_id"] = self.tax_id
        return data


@dataclass
class ZohoInvoiceCreate:
    customer_id: str
    invoice_number: str
    date: str
    line_items: List[ZohoInvoiceItemInput]
    currency_code: str = "INR"
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ZohoInvoiceCreate":
        for key in ("customer_id", "invoice_number", "date"):
            if not payload.get(key):
                raise ValueError(f"ZohoInvoiceCreate requires '{key}'")
        raw_items = payload.get("line_items", [])
        if not raw_items:
            raise ValueError("ZohoInvoiceCreate requires at least one item in 'line_items'")
        items = [ZohoInvoiceItemInput(
            item_id=str(item["item_id"]), rate_paise=int(item["rate_paise"]),
            quantity=int(item.get("quantity", 1)), description=item.get("description", ""), tax_id=item.get("tax_id"),
        ) for item in raw_items]
        return cls(str(payload["customer_id"]), str(payload["invoice_number"]), str(payload["date"]), items,
                   payload.get("currency_code", "INR"), payload.get("notes", ""))

    def to_zoho_json(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "customer_id": self.customer_id, "invoice_number": self.invoice_number, "date": self.date,
            "currency_code": self.currency_code, "line_items": [item.to_zoho_dict() for item in self.line_items],
        }
        if self.notes:
            data["notes"] = self.notes
        return data
