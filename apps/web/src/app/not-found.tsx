"use client";

import Link from "next/link";
import { Search } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-[var(--canvas)] flex-col text-center p-6">
      <div className="w-16 h-16 bg-[var(--royal)] rounded-[10px] flex items-center justify-center text-white font-bold text-2xl mb-6">
        f
      </div>
      <h1 className="text-xl font-semibold text-[var(--text)] mb-2">Page not found</h1>
      <p className="text-[13px] text-[var(--muted)] max-w-[280px] mb-8">
        The route you requested does not exist or you do not have permission to view it.
      </p>
      <div className="flex items-center gap-3">
        <Link 
          href="/" 
          className="h-9 px-4 bg-white border border-[var(--hairline)] hover:bg-[var(--hover)] text-[var(--text)] rounded-[6px] text-[13px] font-medium transition-colors flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--royal)]"
        >
          Return Home
        </Link>
        <button 
          onClick={() => window.dispatchEvent(new Event("open-command-palette"))}
          className="h-9 px-4 bg-[var(--royal)] hover:bg-[var(--royal-hover)] text-white rounded-[6px] text-[13px] font-medium transition-colors flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--royal)]"
        >
          <Search className="w-4 h-4" />
          Jump to... <span className="opacity-70 font-mono text-[10px] ml-1">⌘K</span>
        </button>
      </div>
    </div>
  );
}
