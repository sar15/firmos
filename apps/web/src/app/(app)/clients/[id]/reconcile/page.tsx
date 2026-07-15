"use client";

import { useParams } from "next/navigation";
import { ReconcileClient } from "@/features/reconciliation/components/ReconcileClient";

export default function ClientReconciliationPage() {
  const params = useParams<{ id: string }>();

  return <ReconcileClient clientId={params.id} />;
}
