"use client";

import { useState } from "react";
import { Upload } from "lucide-react";
import { uploadDocument } from "@/features/documents/documents.api";
import { addItrSource } from "./workpapers.api";

const FIELDS:Record<string,[string,string][]>={
  AIS:[["reported_income_paise","Reported income"],["other_income_paise","Other income"],["capital_gains_paise","Capital gains"],["bank_credits_paise","Reported bank credits"]],
  TIS:[["reported_income_paise","Reported income"]],
  "26AS":[["tds_paise","TDS"],["tcs_paise","TCS"]],
  FORM16:[["salary_income_paise","Salary income"],["deductions_paise","Deductions"],["tds_paise","TDS"]],
  FORM16A:[["other_income_paise","Other income"],["tds_paise","TDS"]],
  BOOKS:[["reported_income_paise","Books income"],["business_income_paise","Business income"],["deductions_paise","Deductions"],["advance_tax_paise","Advance tax"],["self_assessment_tax_paise","Self-assessment tax"]],
  BANK:[["bank_credits_paise","Bank credits"]],EVIDENCE:[["reported_income_paise","Supported amount"]],
};

export function ItrSourceForm({workspaceId,clientId,clientName,pan,onSaved}:{workspaceId:string;clientId:string;clientName:string;pan:string;onSaved:()=>Promise<void>}){
  const [type,setType]=useState("AIS");const [period,setPeriod]=useState("");const [version,setVersion]=useState("1");
  const [amounts,setAmounts]=useState<Record<string,string>>({});const [file,setFile]=useState<File|null>(null);
  const [busy,setBusy]=useState(false);const [error,setError]=useState("");
  const save=async()=>{if(!file)return;setBusy(true);setError("");try{const document=await uploadDocument(file,clientId,clientName);
    const extracted=Object.fromEntries(FIELDS[type].map(([key])=>[key,Math.round(Number(amounts[key]||0)*100)]));
    await addItrSource(workspaceId,{source_type:type,source_period:period,taxpayer_pan:pan,source_version:version,document_id:document.id,extracted_values:extracted});
    setFile(null);setAmounts({});await onSaved();}catch(caught){setError(caught instanceof Error?caught.message:"Source could not be added")}finally{setBusy(false)}};
  return <div className="mt-6 border-t pt-5"><h3 className="text-sm font-semibold">Add classified source</h3><p className="mt-1 text-xs text-[var(--muted)]">Upload the evidence and enter its verified summary values in rupees.</p>
    <div className="mt-4 grid gap-3 sm:grid-cols-3"><label className="text-xs text-[var(--muted)]">Source<select value={type} onChange={event=>{setType(event.target.value);setAmounts({})}} className="mt-1 h-11 w-full rounded-md border bg-white px-3 text-sm">{Object.keys(FIELDS).map(item=><option key={item}>{item}</option>)}</select></label>
      <label className="text-xs text-[var(--muted)]">Source period<input value={period} onChange={event=>setPeriod(event.target.value)} placeholder="FY 2025-26" className="mt-1 h-11 w-full rounded-md border px-3 text-sm"/></label>
      <label className="text-xs text-[var(--muted)]">Version<input value={version} onChange={event=>setVersion(event.target.value)} className="mt-1 h-11 w-full rounded-md border px-3 text-sm"/></label></div>
    <div className="mt-3 grid gap-3 sm:grid-cols-2">{FIELDS[type].map(([key,label])=><label key={key} className="text-xs text-[var(--muted)]">{label}<input type="number" min="0" step="0.01" value={amounts[key]||""} onChange={event=>setAmounts(current=>({...current,[key]:event.target.value}))} className="mt-1 h-11 w-full rounded-md border px-3 text-sm"/></label>)}</div>
    <label className="mt-3 block text-xs text-[var(--muted)]">Evidence file<input type="file" onChange={event=>setFile(event.target.files?.[0]||null)} className="mt-1 block min-h-11 w-full rounded-md border bg-white p-2 text-sm"/></label>
    {error&&<p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}<button disabled={busy||!file||!period.trim()||!version.trim()} onClick={save} className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-md border px-4 text-sm font-medium disabled:opacity-50"><Upload className="h-4 w-4"/>{busy?"Adding source…":"Upload and classify"}</button>
  </div>;
}
