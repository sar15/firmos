"""Classification API routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_current_firm, FirmContext, get_db

router = APIRouter(prefix="/api/classify", tags=["classify"])

class ExpenseHeadRequest(BaseModel):
    description: str
    vendor_name: str = ""
    amount_paise: int = 0

@router.post("/expense-head")
async def classify_expense_head(
    req: ExpenseHeadRequest,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    """Suggest an expense head based on description/vendor."""
    desc = req.description.lower()
    vendor = req.vendor_name.lower()
    
    coa_list = []
    
    # Attempt to fetch real CoA from Zoho
    if db_pool:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT access_token_enc, refresh_token_enc, external_account_id FROM connections WHERE firm_id = $1 AND connector_id = 'c1'",
                firm.firm_id
            )
            if row and row["access_token_enc"]:
                from core.security import decrypt_token
                from connectors.zoho_books.client import ZohoClient
                from connectors.zoho_books.sync import list_accounts
                
                access_token = decrypt_token(row["access_token_enc"])
                client = ZohoClient(access_token, row["refresh_token_enc"], row["external_account_id"])
                
                try:
                    acc_res = await list_accounts(client)
                    coa_list = acc_res.get("chartofaccounts", [])
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to fetch CoA from Zoho: {e}")
                    
    head = "General Expenses"
    account_id = None
    
    if coa_list:
        # Filter expense accounts
        expenses = [a for a in coa_list if a.get("account_type") in ("expense", "cost_of_goods_sold", "other_expense")]
        
        # Simple heuristic matching against real CoA names
        keywords = {
            "software": ["software", "it", "computer", "technology"],
            "travel": ["travel", "accommodation", "hotel"],
            "meal": ["meal", "food", "entertainment", "refreshment"],
            "office": ["office", "stationery", "printing", "supply"],
            "legal": ["legal", "professional", "audit", "consult"],
            "ad": ["advertising", "marketing", "promotion"]
        }
        
        matched_category = None
        if "software" in desc or "aws" in vendor or "amazon" in vendor or "cloud" in desc or "saas" in desc:
            matched_category = "software"
        elif "travel" in desc or "flight" in desc or "hotel" in desc or "makemytrip" in vendor:
            matched_category = "travel"
        elif "meal" in desc or "food" in desc or "restaurant" in desc or "zomato" in vendor or "swiggy" in vendor:
            matched_category = "meal"
        elif "office" in desc or "supply" in desc or "stationery" in desc:
            matched_category = "office"
        elif "legal" in desc or "consult" in desc or "audit" in desc or "professional" in desc:
            matched_category = "legal"
        elif "ad" in desc or "marketing" in desc or "facebook" in vendor or "google" in vendor:
            matched_category = "ad"
            
        if matched_category:
            # Find the best match in the client's actual CoA
            for acc in expenses:
                acc_name_lower = acc.get("account_name", "").lower()
                if any(kw in acc_name_lower for kw in keywords[matched_category]):
                    head = acc.get("account_name")
                    account_id = acc.get("account_id")
                    break
                    
        # Fallback to first general expense if no match
        if not account_id and expenses:
            for acc in expenses:
                if "general" in acc.get("account_name", "").lower() or "misc" in acc.get("account_name", "").lower():
                    head = acc.get("account_name")
                    account_id = acc.get("account_id")
                    break
    else:
        # Fallback to mock rules if Zoho is not connected
        if "software" in desc or "aws" in vendor or "amazon" in vendor or "cloud" in desc or "saas" in desc:
            head = "Software & Cloud Services"
        elif "travel" in desc or "flight" in desc or "hotel" in desc or "makemytrip" in vendor:
            head = "Travel & Accommodation"
        elif "meal" in desc or "food" in desc or "restaurant" in desc or "zomato" in vendor or "swiggy" in vendor:
            head = "Meals & Entertainment"
        elif "office" in desc or "supply" in desc or "stationery" in desc:
            head = "Office Supplies"
        elif "legal" in desc or "consult" in desc or "audit" in desc or "professional" in desc:
            head = "Legal & Professional Fees"
        elif "ad" in desc or "marketing" in desc or "facebook" in vendor or "google" in vendor:
            head = "Advertising & Marketing"
        else:
            head = "General Expenses"
            
    return {
        "ok": True,
        "suggested_head": head,
        "account_id": account_id,
        "confidence": "HIGH" if head != "General Expenses" else "LOW"
    }
