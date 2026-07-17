import { CheckCircle2, FileText } from "lucide-react";
import { SalesRegisterRow } from "./registers.types";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const format = (paise: number) => money.format(paise / 100);

export function SalesRegisterTable({ rows, period }: { rows: SalesRegisterRow[]; period: string }) {
  const totals = rows.reduce((sum, row) => ({ taxable: sum.taxable + row.taxablePaise,
    tax: sum.tax + row.taxTotalPaise, total: sum.total + row.totalPaise }), { taxable: 0, tax: 0, total: 0 });
  return (
    <section className="mt-8" aria-labelledby="sales-summary">
      <div className="grid gap-px overflow-hidden rounded-xl border border-[var(--hairline)] bg-[var(--hairline)] sm:grid-cols-3">
        {[["Taxable value",totals.taxable],["Output GST",totals.tax],["Invoice total",totals.total]].map(([label,value]) =>
          <div key={String(label)} className="bg-white px-5 py-4"><p className="text-xs font-medium text-[var(--muted)]">{label}</p><p className="mt-2 font-mono text-xl font-semibold tabular-nums text-[var(--text)]">{format(Number(value))}</p></div>)}
      </div>
      <div className="mt-6 flex items-end justify-between gap-4">
        <div><h2 id="sales-summary" className="text-lg font-semibold text-[var(--text)]">{period}</h2><p className="mt-1 text-sm text-[var(--muted)]">{rows.length} verified invoice{rows.length === 1 ? "" : "s"}</p></div>
        <p className="text-xs text-[var(--muted)]">Amounts in INR</p>
      </div>
      <div className="mt-3 overflow-x-auto rounded-xl border border-[var(--hairline)] bg-white">
        <table className="w-full min-w-[900px] border-collapse text-left text-sm">
          <thead className="bg-[var(--panel)] text-xs uppercase tracking-[0.08em] text-[var(--muted)]"><tr>
            <th className="px-4 py-3 font-semibold">Invoice</th><th className="px-4 py-3 font-semibold">Customer</th>
            <th className="px-4 py-3 font-semibold">Place of supply</th><th className="px-4 py-3 text-right font-semibold">Taxable</th>
            <th className="px-4 py-3 text-right font-semibold">GST</th><th className="px-4 py-3 text-right font-semibold">Total</th><th className="px-4 py-3 font-semibold">Evidence</th>
          </tr></thead>
          <tbody>{rows.map(row => <tr key={row.id} className="border-t border-[var(--hairline)] hover:bg-[var(--hover)]">
            <td className="px-4 py-4"><p className="font-medium text-[var(--text)]">{row.invoiceNumber}</p><p className="mt-1 font-mono text-xs text-[var(--muted)]">{row.invoiceDate}</p></td>
            <td className="px-4 py-4"><p className="font-medium text-[var(--text)]">{row.customerName}</p><p className="mt-1 font-mono text-xs text-[var(--muted)]">{row.customerGstin || "GSTIN not supplied"}</p></td>
            <td className="px-4 py-4 text-[var(--text)]">{row.placeOfSupply || "Needs review"}</td>
            <td className="px-4 py-4 text-right font-mono tabular-nums">{format(row.taxablePaise)}</td><td className="px-4 py-4 text-right font-mono tabular-nums">{format(row.taxTotalPaise)}</td>
            <td className="px-4 py-4 text-right font-mono font-semibold tabular-nums">{format(row.totalPaise)}</td>
            <td className="px-4 py-4"><span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium ${row.verified ? "bg-[var(--royal-tint)] text-[var(--royal)]" : "bg-[var(--amber-tint)] text-[var(--amber)]"}`}>
              {row.verified ? <CheckCircle2 className="h-3.5 w-3.5" /> : <FileText className="h-3.5 w-3.5" />}{row.verified ? "Read-back" : row.provider}</span></td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}
