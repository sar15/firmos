"""WhiteBooks GSP client — implements GstFilingProvider.

WhiteBooks is a licensed GST Suvidita Provider. Uses the GSTN-standard 2-step
OTP handshake (otprequest → authtoken) for taxpayer auth.
Auth: taxpayer username + OTP → auth_token (6hr TTL).
All GSTN-standard payloads — no guessing.

Base URLs:
  Test:  https://apisandbox.whitebooks.in
  Prod:  https://api.whitebooks.in
"""

import logging

import httpx

from core.config import settings
from connectors.gst_filing.types import (
    GstinDetails,
    Gstr2bData,
    Gstr2bSupplierEntry,
    ReconReport,
    PurchaseRow,
)
from connectors.gst_filing.base import ManualFilingRequiredError
from core.money import rupees_to_paise

logger = logging.getLogger(__name__)

# ponytail: single shared client, no pool management for single-user MVP
_http = httpx.AsyncClient(timeout=60.0)

class WhiteBooksGspClient:
    """WhiteBooks GSP — implements GstFilingProvider protocol.
    Uses standard GSTN 2-step authentication.
    """

    def __init__(
        self,
        gstin: str,
        username: str = "",
        auth_token: str = "",
        txn: str = "",
    ):
        self._gstin = gstin
        self._username = username
        self._auth_token = auth_token
        self._txn = txn
        self._base = settings.gsp_base_url or "https://apisandbox.whitebooks.in"
        self._email = settings.whitebooks_email
        self._ip = "127.0.0.1"
        self._state_cd = gstin[:2] if gstin else "33"

    def _headers(self, include_txn: bool = False, include_auth: bool = False) -> dict:
        """Standard headers for all WhiteBooks GSTN API calls."""
        h = {
            "Accept": "application/json",
            "client_id": settings.gsp_api_key,
            "client_secret": settings.gsp_api_secret,
            "gst_username": self._username,
            "state_cd": self._state_cd,
            "ip_address": self._ip,
        }
        if include_txn and self._txn:
            h["txn"] = self._txn
        if include_auth and self._auth_token:
            h["auth-token"] = self._auth_token
        return h

    async def logout(self, username: str = "") -> None:
        """Step 0: Revoke existing session token / logout from GSTN via GSP."""
        uname = username or self._username
        if not uname:
            return
        try:
            resp = await _http.get(
                f"{self._base}/authentication/logout",
                headers=self._headers(include_txn=True, include_auth=True),
                params={"email": self._email, "username": uname},
            )
            logger.info("WhiteBooks logout completed")
        except Exception:
            logger.debug("WhiteBooks logout did not complete")
        finally:
            self._auth_token = ""
            self._txn = ""

    async def request_otp(self, username: str) -> str:
        """Step 1: Request OTP. Returns txn."""
        self._username = username
        resp = await _http.get(
            f"{self._base}/authentication/otprequest",
            headers=self._headers(),
            params={"email": self._email},
        )
        resp.raise_for_status()
        data = resp.json()
        if str(data.get("status_cd")) == "0" or "error" in data:
            err = data.get("error", {})
            err_msg = err.get("message", str(data)) if isinstance(err, dict) else str(err)
            raise ValueError(f"OTP Request Error [{err.get('error_cd', '')}]: {err_msg}")
        self._txn = data.get("header", {}).get("txn", "") or data.get("txn", "")
        return self._txn

    async def authenticate(self, username: str, otp: str = "575757", return_raw: bool = False):
        """Step 2: Authenticate with OTP to get auth_token. Retries with logout if session stuck."""
        if not self._txn:
            try:
                await self.request_otp(username)
            except Exception:
                logger.warning("request_otp failed; attempting logout and retry")
                await self.logout(username)
                await self.request_otp(username)

        try:
            resp = await _http.get(
                f"{self._base}/authentication/authtoken",
                headers=self._headers(include_txn=True),
                params={"email": self._email, "otp": otp},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.warning("authtoken failed; attempting logout and full retry")
            await self.logout(username)
            await self.request_otp(username)
            resp = await _http.get(
                f"{self._base}/authentication/authtoken",
                headers=self._headers(include_txn=True),
                params={"email": self._email, "otp": otp},
            )
            resp.raise_for_status()
            data = resp.json()

        # Check body, header, or nested data for the token
        self._auth_token = (
            data.get("auth-token") or data.get("authtoken") or 
            data.get("header", {}).get("auth-token") or data.get("header", {}).get("authtoken") or ""
        )
        if not self._auth_token and isinstance(data.get("data"), dict):
            self._auth_token = data["data"].get("auth-token") or data["data"].get("authtoken") or ""
        if not self._auth_token and isinstance(data.get("data"), str):
            self._auth_token = data["data"]

        logger.info("WhiteBooks GSP authentication completed")
        if return_raw:
            return self._auth_token, data
        return self._auth_token

    async def verify_gstin(self, gstin: str) -> GstinDetails:
        """Verify a GSTIN via the public search API."""
        resp = await _http.get(
            f"{self._base}/taxpayerapi/v0.2/search",
            headers=self._headers(include_txn=True, include_auth=True),
            params={"email": self._email, "action": "TP", "gstin": gstin},
        )
        resp.raise_for_status()
        data = resp.json()
        tp = data.get("data", data)
        return GstinDetails(
            gstin=gstin,
            legal_name=tp.get("lgnm", ""),
            trade_name=tp.get("tradeNam", ""),
            status=tp.get("sts", ""),
            state_code=tp.get("stcd", gstin[:2]),
            registration_date=tp.get("rgdt", ""),
        )

    async def fetch_2b(self, gstin: str, period: str) -> Gstr2bData:
        """Fetch GSTR-2B for a return period (MMYYYY)."""
        resp = await _http.get(
            f"{self._base}/taxpayerapi/v2.0/returns/gstr2b",
            headers=self._headers(include_txn=True, include_auth=True),
            params={"email": self._email, "gstin": gstin, "ret_period": period},
        )
        resp.raise_for_status()
        raw = resp.json()

        # Parse B2B section into canonical entries
        entries = []
        b2b = raw.get("data", {}).get("docdata", {}).get("b2b", [])
        for supplier in b2b:
            ctin = supplier.get("ctin", "")
            trdnm = supplier.get("trdnm", "")
            for inv in supplier.get("inv", []):
                # Sum up tax across items
                igst = cgst = sgst = taxable = 0
                for item in inv.get("items", []):
                    igst += rupees_to_paise(item.get("igst", 0))
                    cgst += rupees_to_paise(item.get("cgst", 0))
                    sgst += rupees_to_paise(item.get("sgst", 0))
                    taxable += rupees_to_paise(item.get("txval", 0))

                entries.append(Gstr2bSupplierEntry(
                    supplier_gstin=ctin,
                    supplier_name=trdnm,
                    invoice_number=inv.get("inum", ""),
                    invoice_date=inv.get("dt", ""),
                    invoice_value_paise=rupees_to_paise(inv.get("val", 0)),
                    taxable_value_paise=taxable,
                    igst_paise=igst,
                    cgst_paise=cgst,
                    sgst_paise=sgst,
                    itc_available=inv.get("itcavl", "Y") == "Y",
                ))

        return Gstr2bData(
            gstin=gstin,
            period=period,
            entries=entries,
            raw_response=raw,
        )

    async def reconcile_2b(
        self,
        gstin: str,
        period: str,
        purchase_ledger: list[PurchaseRow],
    ) -> ReconReport:
        from connectors.gst_filing.whitebooks.reconcile import reconcile_gstr2b

        return await reconcile_gstr2b(self, gstin, period, purchase_ledger)

    async def save_gstr3b(self, *_args, **_kwargs) -> None:
        raise ManualFilingRequiredError("GSTR-3B portal writes are disabled; export the manual filing pack.")

    async def file_gstr3b(self, *_args, **_kwargs) -> None:
        raise ManualFilingRequiredError("GSTR-3B filing is manual in V1; record portal acknowledgement separately.")

    async def file_gstr1(self, *_args, **_kwargs) -> None:
        raise ManualFilingRequiredError("GSTR-1 filing is manual in V1.")
