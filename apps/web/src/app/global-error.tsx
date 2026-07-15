"use client";

import { useEffect } from "react";
import { AlertCircle } from "lucide-react";

export default function GlobalError({
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
    <html lang="en">
      <body>
        <div className="flex h-screen w-screen items-center justify-center bg-[var(--canvas)] flex-col text-center p-6">
          <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center text-red-600 mb-4">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h1 className="text-lg font-semibold text-[var(--text)] mb-2">Something went wrong</h1>
          <p className="text-[13px] text-[var(--muted)] max-w-[280px] mb-6">
            A critical error occurred. If this persists, please contact support.
          </p>
          <button
            onClick={() => reset()}
            className="h-9 px-6 bg-[var(--royal)] hover:bg-[var(--royal-hover)] text-white rounded-[6px] text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--royal)]"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
