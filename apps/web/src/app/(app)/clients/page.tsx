import { ClientsList } from "@/features/clients/ClientsList";

export default function ClientsPage() {
  return (
    <div className="flex-1 flex flex-col h-full bg-[var(--canvas)] overflow-hidden">
      <ClientsList />
    </div>
  );
}
