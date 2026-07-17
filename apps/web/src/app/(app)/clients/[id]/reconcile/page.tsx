import { ReconcileClient } from "@/features/reconciliation/components/ReconcileClient";

const ClientReconciliationPage = async ({ params }: { params: Promise<{ id: string }> }) => {
  const { id } = await params;
  return <ReconcileClient clientId={id} />;
};

export default ClientReconciliationPage;
