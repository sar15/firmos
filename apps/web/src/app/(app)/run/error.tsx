"use client";

import { useEffect } from "react";
import { AlertCircle, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex-1 w-full h-full flex items-center justify-center bg-[var(--canvas)]">
      <div className="flex flex-col items-center max-w-sm text-center">
        <div className="w-10 h-10 rounded-full bg-[var(--red)]/10 flex items-center justify-center mb-4">
          <AlertCircle className="w-5 h-5 text-[var(--red)]" />
        </div>
        <h2 className="text-[15px] font-semibold text-[var(--text)] mb-1">Something went wrong</h2>
        <p className="text-[13px] text-[var(--muted)] mb-5">
          {error.message || "An unexpected error occurred while loading this page."}
        </p>
        <Button onClick={() => reset()} className="bg-[var(--royal)] text-white hover:bg-[var(--royal-hover)] border-none h-8 px-4 rounded-[6px] text-[13px] flex items-center gap-2 transition-all">
          <RefreshCcw className="w-3.5 h-3.5" />
          Try again
        </Button>
      </div>
    </div>
  );
}
