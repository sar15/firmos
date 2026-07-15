import { getAuthHeaders } from "@/lib/auth";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, headers: { ...await getAuthHeaders(), ...(init?.body ? { "Content-Type": "application/json" } : {}) }, cache: "no-store" });
  if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail || "The workflow could not be updated."); }
  return res.json();
}

export type GstWorkpaper = { id:string; return_type:"GSTR1"|"GSTR3B"; period:string; version:number; status:string; stale:boolean; tables:Record<string,{source_total_paise:number;adjustment_paise:number;total_paise:number}>; exceptions:{code:string;message:string}[] };
export type GstAdjustment={adjustment_id:string;table_key:string;component:string;amount_paise:number;reason:string};
export const prepareGst=(client_id:string,period:string,return_type:"GSTR1"|"GSTR3B",adjustments:GstAdjustment[]=[])=>request<GstWorkpaper>("/api/gst/workpapers",{method:"POST",body:JSON.stringify({client_id,period,return_type,adjustments})});
export const getGst=(client_id:string,period:string,return_type:"GSTR1"|"GSTR3B")=>request<{workpaper:GstWorkpaper}>(`/api/gst/workpapers/latest?${new URLSearchParams({client_id,period,return_type})}`);
export const approveGst=(id:string)=>request<GstWorkpaper>(`/api/gst/workpapers/${id}/approve`,{method:"POST"});
export const packGst=(id:string)=>request<GstWorkpaper>(`/api/gst/workpapers/${id}/pack`,{method:"POST"});
export const activateGstRules=()=>request("/api/gst/rules/activate-official-defaults",{method:"POST"});

export type ItrWorkspace={id:string;assessment_year:string;taxpayer_pan:string;taxpayer_name:string;status:string;stale:boolean;computation:Record<string,number>;filing_pack?:Record<string,unknown>};
export type ItrReconciliation={category:string;status:string;difference_paise:number};
export const createItr=(client_id:string,assessment_year:string,taxpayer_pan:string,taxpayer_name:string)=>request<ItrWorkspace>("/api/itr/workspaces",{method:"POST",body:JSON.stringify({client_id,assessment_year,taxpayer_pan,taxpayer_name})});
export const authorizeItr=(id:string,authorized_by:string,evidence_reference:string)=>request(`/api/itr/workspaces/${id}/authorizations`,{method:"POST",body:JSON.stringify({authorized_by,evidence_reference,permissions:["VIEW","PREPARE","APPROVE"],granted_at:new Date().toISOString()})});
export const getItr=(client_id:string,assessment_year:string)=>request<{workspace:ItrWorkspace;sources:{source_type:string;source_version:string}[];reconciliation:ItrReconciliation[];authorizations:{authorized_by:string;evidence_reference:string}[]}>(`/api/itr/workspaces/latest?${new URLSearchParams({client_id,assessment_year})}`);
export const reconcileItr=(id:string)=>request<ItrReconciliation[]>(`/api/itr/workspaces/${id}/reconcile`,{method:"POST"});
export const activateItrRule=(assessmentYear:string)=>request(`/api/itr/rules/${assessmentYear}/activate-official-default`,{method:"POST"});
export const addItrSource=(id:string,source:{source_type:string;source_period:string;taxpayer_pan:string;source_version:string;document_id?:string;extracted_values:Record<string,number>})=>request(`/api/itr/workspaces/${id}/sources`,{method:"POST",body:JSON.stringify(source)});
export const draftItr=(id:string,regime:"NEW"|"OLD")=>request<ItrWorkspace>(`/api/itr/workspaces/${id}/draft`,{method:"POST",body:JSON.stringify({regime,resident:true})});
export const approveItr=(id:string)=>request<ItrWorkspace>(`/api/itr/workspaces/${id}/approve`,{method:"POST"});
export const packItr=(id:string)=>request<ItrWorkspace>(`/api/itr/workspaces/${id}/pack`,{method:"POST"});
