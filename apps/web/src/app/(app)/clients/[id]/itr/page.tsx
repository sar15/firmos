import { ClientItrWorkspace } from "@/features/compliance/ClientItrWorkspace";

const ItrPage = async ({ params }: { params: Promise<{ id: string }> }) => {
  const { id } = await params;
  return <ClientItrWorkspace clientId={id} />;
};

export default ItrPage;
