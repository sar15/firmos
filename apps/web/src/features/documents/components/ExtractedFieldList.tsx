import React from "react";
import { ExtractedDocument } from "@/types";
import { FieldRow } from "./FieldRow";
import { formatIndianRupee } from "@/lib/formatIndianRupee";

interface ExtractedFieldListProps {
  document: ExtractedDocument;
  onUpdateField: (key: string, value: string) => void;
  onFocusField: (key: string) => void;
  onBlurField: () => void;
  focusedFieldKey: string | null;
}

export function ExtractedFieldList({
  document,
  onUpdateField,
  onFocusField,
  onBlurField,
  focusedFieldKey,
}: ExtractedFieldListProps) {
  const fields = document.fields || [];
  const lineItems = document.lineItems || [];
  const lineItemTotal = lineItems.reduce((acc, item) => acc + (item.amount || 0), 0);

  return (
    <div className="flex flex-col h-full bg-white overflow-y-auto">
      {/* Header */}
      <div className="p-6 border-b border-[var(--hairline)] bg-white sticky top-0 z-20 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
        <h2 className="text-lg font-semibold text-text mb-1 truncate" title={document.vendorName || "Uploaded Document"}>
          {document.vendorName || "Uploaded Document"}
        </h2>
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted">{document.clientName || "Client"}</span>
          <span className="font-mono text-text font-semibold tracking-tight">
            {formatIndianRupee(document.total || 0)}
          </span>
        </div>
      </div>

      {/* Fields */}
      <div className="flex flex-col border-b border-[var(--hairline)]">
        {fields.map((field) => (
          <FieldRow
            key={field.key}
            field={field}
            onUpdate={onUpdateField}
            onFocus={onFocusField}
            onBlur={onBlurField}
            isFocused={focusedFieldKey === field.key}
          />
        ))}
      </div>

      {/* Line Items Table */}
      {lineItems.length > 0 && (
        <div className="p-6">
          <h3 className="text-sm font-medium text-text mb-4">Line Items</h3>
          <div className="rounded border border-[var(--hairline)] bg-white overflow-hidden">
            <table className="w-full text-sm text-left">
              <thead className="bg-hover text-muted text-[10px] uppercase tracking-wider font-medium border-b border-[var(--hairline)]">
                <tr>
                  <th className="px-4 py-2 font-medium">Description</th>
                  <th className="px-4 py-2 font-medium text-center">HSN</th>
                  <th className="px-4 py-2 font-medium text-right">Qty</th>
                  <th className="px-4 py-2 font-medium text-right">Rate</th>
                  <th className="px-4 py-2 font-medium text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--hairline)]">
                {lineItems.map((item, idx) => (
                  <tr key={idx} className="hover:bg-hover/50 transition-colors">
                    <td className="px-4 py-3 text-text">{item.desc}</td>
                    <td className="px-4 py-3 text-muted text-center font-mono text-xs">{item.hsn || "-"}</td>
                    <td className="px-4 py-3 text-slate-700 text-right font-mono tabular-nums text-xs">{item.qty}</td>
                    <td className="px-4 py-3 text-slate-700 text-right font-mono tabular-nums text-xs">
                      {formatIndianRupee(item.rate)}
                    </td>
                    <td className="px-4 py-3 text-text text-right font-mono tabular-nums font-medium text-xs">
                      {formatIndianRupee(item.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-[var(--hairline)] bg-hover/80">
                <tr>
                  <td colSpan={4} className="px-4 py-3 text-right font-medium text-muted text-[11px] uppercase tracking-wider">
                    Total
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums font-bold text-text text-sm">
                    {formatIndianRupee(lineItemTotal)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
