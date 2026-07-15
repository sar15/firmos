import { AuditTable } from "@/features/audit/components/AuditTable";
import { PageHeader } from "@/components/PageHeader";

export default function AuditPage() {
  return (
    <div className="flex flex-col h-[calc(100vh-56px)] bg-white">
      <PageHeader 
        title="Audit Log"
        className="bg-white pt-10 px-8 shrink-0 flex justify-center"
        contentClassName="max-w-[1024px]"
      >
        <p className="text-[13px] text-muted mb-4">
          Immutable trust ledger of all actions and workflows.
        </p>
      </PageHeader>
      
      <div className="flex-1 w-full flex justify-center py-6 px-8 overflow-y-auto">
        <div className="w-full max-w-[1024px] flex flex-col items-start">
          <AuditTable />
        </div>
      </div>
    </div>
  );
}
