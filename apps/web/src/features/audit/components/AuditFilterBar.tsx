import { Download } from "lucide-react";

export function AuditFilterBar() {
  return (
    <div className="mb-6 flex w-full items-center justify-end">
      <button disabled title="Audit export is not available yet" className="flex h-8 cursor-not-allowed items-center gap-2 rounded-[6px] bg-[var(--hairline)] px-4 text-white opacity-60">
        <Download className="h-3.5 w-3.5" />
        <span className="text-[13px] font-medium">Export unavailable</span>
      </button>
    </div>
  );
}
