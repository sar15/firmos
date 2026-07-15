import React from "react";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Agent - firmOS",
  description: "firmOS command center",
};

export default function AgentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="absolute inset-0 flex min-h-0 min-w-0 bg-[var(--canvas)]">
      {children}
    </div>
  );
}
