"use client";

import React from "react";
import { NeedsYouList } from "./NeedsYouList";

export function ContextColumn() {

  return (
    <aside className="w-[340px] bg-[var(--panel)] border-l border-[var(--hairline)] overflow-y-auto p-5 flex flex-col gap-[22px] shrink-0 hidden lg:flex">
      
      <div>
        <NeedsYouList />
      </div>

    </aside>
  );
}
