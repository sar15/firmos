"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { GstWorkspace } from "./GstWorkspace";

export const ClientGstWorkspace = ({ clientId }: { clientId: string }) => (
  <main className="min-h-screen overflow-y-auto bg-[var(--canvas)] px-4 py-6 sm:px-8">
    <div className="mx-auto max-w-5xl">
      <Link href={`/clients/${clientId}`} className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-[var(--muted)]"><ArrowLeft className="h-4 w-4" />Client workspace</Link>
      <header className="my-6 border-b border-[var(--hairline)] pb-6"><p className="text-xs font-semibold uppercase tracking-[.12em] text-[var(--muted)]">Compliance · GST</p><h1 className="mt-2 text-3xl font-semibold tracking-[-.03em]">GST workpapers</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">Build source-linked GSTR-1 and GSTR-3B review snapshots, then create a clearly labelled manual filing pack.</p></header>
      <GstWorkspace clientId={clientId} />
    </div>
  </main>
);
