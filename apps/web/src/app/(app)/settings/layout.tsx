import React from "react";
import { SettingsSidebar } from "@/features/settings/components/SettingsSidebar";

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col h-full bg-[var(--canvas)]">
      <div className="p-6 border-b border-[var(--hairline)] bg-[var(--canvas)] shrink-0">
        <h1 className="text-xl font-semibold text-[var(--text)]">Settings</h1>
        <p className="text-sm text-[var(--muted)] mt-1">Manage your firm&apos;s preferences, billing, and team access.</p>
      </div>
      
      <div className="flex flex-1 min-h-0">
        <div className="w-[240px] border-r border-[var(--hairline)] bg-[var(--canvas)] shrink-0 overflow-y-auto">
          <SettingsSidebar />
        </div>
        <div className="flex-1 overflow-y-auto bg-white">
          {children}
        </div>
      </div>
    </div>
  );
}
