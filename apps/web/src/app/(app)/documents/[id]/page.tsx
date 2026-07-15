import { notFound } from "next/navigation";
import { DocumentReview } from "@/features/documents/components/DocumentReview";
import { getDocument } from "@/features/documents/documents.api";

export const metadata = {
  title: "Review Document | firmOS",
};

// Use an async component to fetch data server-side
export default async function DocumentReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = await params;
  const document = await getDocument(resolvedParams.id);

  if (!document) {
    notFound();
  }

  return <DocumentReview initialDocument={document} />;
}
