import { SearchResults } from "@/features/search/SearchResults";
import { Suspense } from "react";

export default function SearchPage() {
  return (
    <div className="flex-1 flex flex-col h-full bg-[var(--canvas)] overflow-hidden">
      <Suspense fallback={<div className="p-12 text-sm text-[var(--muted)]">Loading search...</div>}>
        <SearchResults />
      </Suspense>
    </div>
  );
}
