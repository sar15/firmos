import { DocumentActionProposal, DocumentMapping } from "../documents.api";

type Candidate = { id: string; label: string };

function Choice({ label, value, options, onChange }: {
  label: string; value?: string; options: Candidate[]; onChange: (value: string) => void;
}) {
  return (
    <label className="flex items-center gap-1 text-xs text-slate-800">{label}
      <select aria-label={label} value={value || ""} onChange={event => onChange(event.target.value)}
        className="min-h-10 rounded border border-amber-300 bg-white px-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--royal)]">
        <option value="">Choose</option>
        {options.map(candidate => <option key={candidate.id} value={candidate.id}>{candidate.label}</option>)}
      </select>
    </label>
  );
}

export function DocumentMappingForm({ proposal, mapping, onChange }: {
  proposal: DocumentActionProposal; mapping: DocumentMapping;
  onChange: (mapping: DocumentMapping) => void;
}) {
  if (proposal.status !== "NEEDS_MAPPING") return null;
  const set = (key: keyof DocumentMapping) => (value: string) => onChange({ ...mapping, [key]: value });
  return (
    <div className="flex max-w-3xl flex-wrap items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2" role="group" aria-label="Required connector mappings">
      {proposal.missing_mappings.includes("vendor_id") && <Choice label="Supplier" value={mapping.vendor_id} options={proposal.vendor_candidates} onChange={set("vendor_id")} />}
      {proposal.missing_mappings.includes("customer_id") && <Choice label="Customer" value={mapping.customer_id} options={proposal.customer_candidates} onChange={set("customer_id")} />}
      {proposal.missing_mappings.includes("account_id") && <Choice label="Expense ledger" value={mapping.account_id} options={proposal.account_candidates} onChange={set("account_id")} />}
      {proposal.missing_mappings.includes("item_id") && <Choice label="Item" value={mapping.item_id} options={proposal.item_candidates} onChange={set("item_id")} />}
      {proposal.missing_mappings.includes("tax_id") && <Choice label="GST tax" value={mapping.tax_id} options={proposal.tax_candidates} onChange={set("tax_id")} />}
      {proposal.missing_mappings.includes("party_ledger") && <Choice label="Supplier ledger" value={mapping.party_ledger} options={proposal.vendor_candidates} onChange={set("party_ledger")} />}
      {proposal.missing_mappings.includes("purchase_ledger") && <Choice label="Purchase ledger" value={mapping.purchase_ledger} options={proposal.account_candidates} onChange={set("purchase_ledger")} />}
      {proposal.missing_mappings.includes("sales_ledger") && <Choice label="Sales ledger" value={mapping.sales_ledger} options={proposal.account_candidates} onChange={set("sales_ledger")} />}
      {proposal.missing_mappings.includes("cgst_ledger") && <Choice label="CGST ledger" value={mapping.cgst_ledger} options={proposal.account_candidates} onChange={set("cgst_ledger")} />}
      {proposal.missing_mappings.includes("sgst_ledger") && <Choice label="SGST ledger" value={mapping.sgst_ledger} options={proposal.account_candidates} onChange={set("sgst_ledger")} />}
      {proposal.missing_mappings.includes("igst_ledger") && <Choice label="IGST ledger" value={mapping.igst_ledger} options={proposal.account_candidates} onChange={set("igst_ledger")} />}
    </div>
  );
}
