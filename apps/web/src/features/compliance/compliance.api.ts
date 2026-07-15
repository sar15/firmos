import { getAuthHeaders } from "@/lib/auth";

export interface Gstr3bCellData {
  txval?: number;
  iamt?: number;
  camt?: number;
  samt?: number;
  csamt?: number;
  payable?: number;
  paid_itc?: number;
  paid_cash?: number;
}

export interface Gstr3bTablesResponse {
  client_id: string;
  period: string;
  tables: {
    table_3_1: Record<string, Gstr3bCellData>;
    table_3_2: Record<string, unknown>;
    table_4: {
      A_itc_available: Record<string, Gstr3bCellData>;
      B_itc_reversed: Record<string, Gstr3bCellData>;
      C_net_itc_available: Gstr3bCellData;
      D_ineligible_itc: Record<string, Gstr3bCellData>;
    };
    table_5: Record<string, unknown>;
    table_6_1: {
      payment_of_tax: Record<string, Gstr3bCellData>;
    };
  };
}

export interface ManualGstPackResponse {
  sales_register: { count: number; total_paise: number; tax_paise: number };
  gstr2b_mismatch_report: { summary: { autoMatched: number; suggested: number; unmatched: number } };
  gstr3b_working: { matched_itc_paise: number; warning: string };
  review_checklist: { item: string; complete: boolean }[];
}

export async function fetchManualGstPack(clientId: string, period: string): Promise<ManualGstPackResponse> {
  const res = await fetch(`/api/connectors/zoho/manual-gst-pack?client_id=${encodeURIComponent(clientId)}&period=${encodeURIComponent(period)}`, { headers: await getAuthHeaders() });
  if (!res.ok) throw new Error("Failed to prepare the manual GST filing pack");
  return res.json();
}

export async function fetchGstr3bTables(clientId: string, period: string): Promise<Gstr3bTablesResponse> {
  const res = await fetch(
    `/api/connectors/zoho/gstr3b-tables?client_id=${encodeURIComponent(clientId)}&period=${encodeURIComponent(period)}`,
    { headers: await getAuthHeaders() }
  );
  if (!res.ok) throw new Error(`Failed to fetch GSTR-3B tables: ${res.statusText}`);
  return res.json();
}

export async function fetchGstr3bJson(clientId: string, period: string, gstin?: string): Promise<Record<string, unknown>> {
  const url = `/api/connectors/zoho/gstr3b-json?client_id=${encodeURIComponent(clientId)}&period=${encodeURIComponent(period)}${gstin ? `&gstin=${encodeURIComponent(gstin)}` : ""}`;
  const res = await fetch(url, { headers: await getAuthHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch GSTR-3B GSTN JSON: ${res.statusText}`);
  return res.json();
}
