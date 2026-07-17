import { ClientGstWorkspace } from "@/features/compliance/ClientGstWorkspace";

const GstPage = async ({ params }: { params: Promise<{ id: string }> }) => {
  const { id } = await params;
  return <ClientGstWorkspace clientId={id} />;
};

export default GstPage;
