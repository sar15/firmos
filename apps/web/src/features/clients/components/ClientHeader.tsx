import Link from "next/link";
import type { Client } from "@/types";

export function ClientHeader({ client }: { client: Client }) {
  return (
    <div className="w-full mb-8 flex flex-col gap-3">
      <h1 className="text-[20px] font-semibold text-text tracking-tight leading-none">
        {client.legalName}
      </h1>
      <p className="text-[13px] text-muted">
        {client.entityType?.replace("_", " ")} <span className="mx-1">·</span> {client.state}
      </p>
      <div className="flex flex-wrap items-center gap-2 mt-1">
        {client.pan && (
          <div className="px-2 py-0.5 bg-hover border border-hairline rounded-[4px] text-[11px] font-medium text-text mono">
            {client.pan}
          </div>
        )}
        {client.gstin && (
          <div className="px-2 py-0.5 bg-hover border border-hairline rounded-[4px] text-[11px] font-medium text-text mono">
            {client.gstin}
          </div>
        )}
        {client.booksProvider && (
          <div className="px-2 py-0.5 bg-hover border border-hairline rounded-[4px] text-[11px] font-medium text-text">
            {client.booksProvider.replace("_", " ")}
          </div>
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        <Link
          href={`/clients/${client.id}/reconcile`}
          className="inline-flex min-h-11 items-center rounded-md bg-royal px-4 text-sm font-medium text-white transition-colors hover:bg-royal/90 focus-ring"
        >
          Reconcile transactions
        </Link>
        <Link
          href={`/clients/${client.id}/purchase-register`}
          className="inline-flex min-h-11 items-center rounded-md border border-hairline px-4 text-sm font-medium text-text transition-colors hover:bg-hover focus-ring"
        >
          Purchase register
        </Link>
        <Link href={`/clients/${client.id}/sales-register`} className="inline-flex min-h-11 items-center rounded-md border border-hairline px-4 text-sm font-medium text-text transition-colors hover:bg-hover focus-ring">Sales register</Link>
        <Link href={`/clients/${client.id}/gst`} className="inline-flex min-h-11 items-center rounded-md border border-hairline px-4 text-sm font-medium text-text transition-colors hover:bg-hover focus-ring">GST workpapers</Link>
        <Link href={`/clients/${client.id}/itr`} className="inline-flex min-h-11 items-center rounded-md border border-hairline px-4 text-sm font-medium text-text transition-colors hover:bg-hover focus-ring">ITR preparation</Link>
      </div>
    </div>
  );
}
