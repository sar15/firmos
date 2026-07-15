"""Pure parsers and balance checks for private bank-statement uploads."""
import io
import logging
from datetime import datetime
from core.money import MoneyParseError, rupees_to_paise

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> str:
    if not date_str:
        return ""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str.strip()


def _safe_paise(value) -> int:
    if value is None or value == "" or value != value:
        return 0
    try:
        return rupees_to_paise(value)
    except MoneyParseError:
        return 0


def _transaction(row: dict, source_row: int | None = None, source_page: int | None = None) -> dict | None:
    date = str(row.get("date", row.get("txn date", row.get("value date", ""))))
    description = str(row.get("description", row.get("particulars", row.get("narration", ""))))
    if not date or not description or description == "nan":
        return None
    debit = _safe_paise(row.get("withdrawal", row.get("debit")))
    credit = _safe_paise(row.get("deposit", row.get("credit")))
    raw_amount = _safe_paise(row.get("amount", 0))
    if debit and credit:
        net_amount = credit - debit
        amount, txn_type = abs(net_amount), "CREDIT" if net_amount > 0 else "DEBIT"
    elif debit:
        amount, txn_type = debit, "DEBIT"
    elif credit:
        amount, txn_type = credit, "CREDIT"
    else:
        amount, txn_type = abs(raw_amount), "CREDIT" if raw_amount > 0 else "DEBIT"
    reference = str(row.get("ref no", row.get("reference", row.get("chq no", "")))).strip()
    return {
        "txn_date": _parse_date(date), "description": description.strip(), "amount": amount,
        "txn_type": txn_type,
        "running_balance": _safe_paise(row.get("balance", row.get("closing balance", 0))),
        "ref_no": "" if reference == "nan" else reference,
        "value_date": _parse_date(str(row.get("value date", ""))),
        "source_row": source_row, "source_page": source_page,
    }


def parse_csv_or_excel(content: bytes, filename: str) -> list[dict]:
    """Parse CSV or Excel into normalized transaction records."""
    import pandas as pd

    frame = pd.read_excel(io.BytesIO(content)) if filename.endswith((".xlsx", ".xls")) else pd.read_csv(io.BytesIO(content))
    frame.columns = [column.lower().strip() for column in frame.columns]
    return [item for index, row in frame.iterrows() if (item := _transaction(row.to_dict(), int(index) + 2))]


def parse_pdf_digital(content: bytes) -> list[dict]:
    """Extract transactions from digital PDF tables without provider calls."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed, cannot parse digital PDF")
        return []
    transactions = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables():
                if not table or len(table) < 2:
                    continue
                headers = [str(header).lower().strip() if header else "" for header in table[0]]
                for row_number, row in enumerate(table[1:], start=2):
                    if len(row) == len(headers):
                        item = _transaction(dict(zip(headers, row)), row_number, page_number)
                        if item:
                            transactions.append(item)
    return transactions


def validate_running_balance(transactions: list[dict]) -> dict:
    """Identify balance discontinuities, allowing one-rupee rounding drift."""
    if not transactions or not transactions[0].get("running_balance"):
        return {"valid": True, "breaks": [], "reason": "No balance data to validate"}
    breaks = []
    for index, transaction in enumerate(transactions[1:], start=1):
        previous = transactions[index - 1]["running_balance"]
        expected = previous + transaction["amount"] if transaction["txn_type"] == "CREDIT" else previous - transaction["amount"]
        if abs(expected - transaction["running_balance"]) > 100:
            breaks.append({"row": index, "expected_balance": expected, "actual_balance": transaction["running_balance"], "description": transaction["description"]})
    return {"valid": not breaks, "breaks": breaks[:10], "checked_rows": len(transactions)}
