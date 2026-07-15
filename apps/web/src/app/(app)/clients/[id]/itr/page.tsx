"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { ItrWorkspace } from "@/features/compliance/ItrWorkspace";

export default function ItrPage() {
  const id = useParams()?.id as string;
  return <main className="min-h-screen overflow-y-auto bg-[var(--canvas)] px-4 py-6 sm:px-8">
    <div className="mx-auto max-w-5xl">
      <Link href={`/clients/${id}`} className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-[var(--muted)]"><ArrowLeft className="h-4 w-4" />Client workspace</Link>
      <header className="my-6 border-b pb-6"><p className="text-xs font-semibold uppercase tracking-[.12em] text-[var(--muted)]">Compliance · Income tax</p><h1 className="mt-2 text-3xl font-semibold tracking-[-.03em]">ITR preparation</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">An assessment-year workspace for authorization, evidence reconciliation and manual filing preparation.</p></header>
      <ItrWorkspace clientId={id} />
    </div>
  </main>;
}
