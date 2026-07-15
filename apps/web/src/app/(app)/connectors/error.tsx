"use client";

import { useEffect } from "react";
import { AlertCircle } from "lucide-react";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex h-full w-full items-center justify-center bg-[var(--canvas)] flex-col text-center p-6">
      <div className="w-12 h-12 bg-red-50 border border-red-100 rounded-full flex items-center justify-center text-red-500 mb-4">
        <AlertCircle className="w-5 h-5" />
      </div>
      <h2 className="text-[15px] font-semibold text-[var(--text)] mb-1">Something went wrong</h2>
      <p className="text-[13px] text-[var(--muted)] max-w-[320px] mb-6">
        We encountered an unexpected error while loading this page.
      </p>
      <button
        onClick={() => reset()}
        className="h-8 px-4 bg-[var(--royal)] hover:bg-[var(--royal-hover)] text-white rounded-[6px] text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--royal)]"
      >
        Try again
      </button>
    </div>
  );
}
