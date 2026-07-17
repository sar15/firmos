import { ClientProfileWorkspace } from "@/features/clients/components/ClientProfileWorkspace";

const ClientProfilePage = async ({ params }: { params: Promise<{ id: string }> }) => {
  const { id } = await params;
  return <ClientProfileWorkspace clientId={id} />;
};

export default ClientProfilePage;
