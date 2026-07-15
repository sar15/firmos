"""Private upload contract using only the standard library."""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 50


class UploadRejected(ValueError):
    def __init__(self, code: str, message: str, state: str, user_action: str):
        super().__init__(message)
        self.code, self.state, self.user_action = code, state, user_action


@dataclass(frozen=True)
class SafeUpload:
    filename: str
    mime_type: str
    file_type: str
    extension: str
    page_count: int


def _xlsx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
        return "[Content_Types].xml" in names and "xl/workbook.xml" in names
    except zipfile.BadZipFile:
        return False


def inspect_upload(filename: str, claimed_mime: str, data: bytes) -> SafeUpload:
    """Validate size, signature, encryption and page count before storage."""
    name = Path(filename or "document").name[:240]
    if not data:
        raise UploadRejected("EMPTY_FILE", "The uploaded file is empty.", "CORRUPT", "Choose the original invoice file and try again.")
    if len(data) > MAX_BYTES:
        raise UploadRejected("FILE_OVERSIZED", "The file exceeds the 20 MB limit.", "OVERSIZED", "Compress or split the document, then upload again.")
    if data.startswith(b"%PDF-"):
        mime, kind, extension = "application/pdf", "pdf", "pdf"
        if b"%%EOF" not in data[-4096:]:
            raise UploadRejected("PDF_CORRUPT", "The PDF is incomplete or corrupt.", "CORRUPT", "Export the original PDF again and retry.")
        if b"/Encrypt" in data[-200_000:]:
            raise UploadRejected("PDF_PASSWORD_PROTECTED", "Password-protected PDFs cannot be extracted.", "PASSWORD_PROTECTED", "Upload an unlocked copy.")
        pages = max(1, len(re.findall(rb"/Type\s*/Page(?!s)\b", data)))
    elif data.startswith(b"\xff\xd8\xff"):
        mime, kind, extension, pages = "image/jpeg", "image", "jpg", 1
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime, kind, extension, pages = "image/png", "image", "png", 1
    elif _xlsx(data):
        mime, kind, extension, pages = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "spreadsheet", "xlsx", 1
    else:
        raise UploadRejected("UNSUPPORTED_FILE", "Use PDF, JPEG, PNG, or XLSX.", "UNSUPPORTED", "Export the invoice to a supported format.")
    if pages > MAX_PAGES:
        raise UploadRejected("PAGE_LIMIT_EXCEEDED", f"The document has more than {MAX_PAGES} pages.", "OVERSIZED", "Split the document and upload each invoice separately.")
    normalized_claim = (claimed_mime or "").split(";", 1)[0].strip().lower()
    accepted_claims = {"", "application/octet-stream", mime}
    if extension == "jpg":
        accepted_claims.add("image/jpg")
    if normalized_claim not in accepted_claims:
        raise UploadRejected("MIME_MISMATCH", "The file contents do not match its reported type.", "QUARANTINED", "Re-export the original file and try again.")
    return SafeUpload(name, mime, kind, extension, pages)
