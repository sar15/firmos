"""Manual local check for PDF bank-statement ingestion; requires configured test storage."""
import io

from fastapi.testclient import TestClient
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from api.main import app


def generate_pdf() -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter)
    table = Table([
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["01-06-2026", "Opening Balance", "", "1000.00", "1000.00"],
        ["05-06-2026", "Salary", "", "5000.00", "6000.00"],
    ])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    document.build([table])
    return buffer.getvalue()


def main() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/bank-statements/upload",
            headers={"x-firm-id": "firm-1", "x-client-id": "client-1"},
            files={"file": ("bank_statement.pdf", generate_pdf(), "application/pdf")},
            data={"client_id": "client-1"},
        )
    print(f"Bank upload completed with HTTP {response.status_code}")


if __name__ == "__main__":
    main()
