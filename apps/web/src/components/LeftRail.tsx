"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Users, FileText, LayoutGrid, LogOut, ShieldCheck, Settings } from "lucide-react";
import { getBrowserAuth } from "@/lib/auth";

export function LeftRail({ userEmail }: { userEmail: string }) {
  const pathname = usePathname();
  const initials = userEmail.slice(0, 2).toUpperCase();

  const workItems = [
    { name: "Agent", href: "/agent", icon: Home },
    { name: "Clients", href: "/clients", icon: Users },
    { name: "Documents", href: "/documents", icon: FileText },
  ];

  const systemItems = [
    { name: "Connectors", href: "/connectors", icon: LayoutGrid },
    { name: "Audit log", href: "/audit", icon: ShieldCheck },
    { name: "Settings", href: "/settings/profile", icon: Settings },
  ];

  return (
    <aside className="w-[244px] bg-[var(--panel)] border-r border-[var(--hairline)] flex flex-col shrink-0 h-full p-[18px_14px]">
      {/* Brand */}
      <Link href="/" className="flex items-center gap-[11px] px-2.5 pb-[22px] pt-1 font-semibold text-[16px] tracking-[-0.02em] text-[var(--text)] hover:opacity-90 transition-opacity select-none">
        <div className="w-[26px] h-[26px] rounded-[7px] bg-gradient-to-br from-[var(--royal)] to-[#6B7CF7] flex items-center justify-center text-white text-[13px] shadow-[0_2px_8px_rgba(37,64,217,0.3)]">
          f
        </div>
        firmOS
      </Link>

      <div className="flex flex-col flex-1 overflow-y-auto overflow-x-hidden">
        {/* Work Section */}
        <div className="text-[11px] text-[var(--muted-2)] uppercase tracking-[0.1em] px-2.5 pt-4 pb-2 font-semibold select-none">Work</div>
        <nav className="flex flex-col">
          {workItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href.split('?')[0]) && item.href !== "/agent?filter=approvals" && item.href !== "/agent?filter=reconcile");
            
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-[11px] px-2.5 py-[9px] rounded-[10px] cursor-pointer text-[14px] font-medium transition-all duration-150 ease-out mb-[1px] group select-none ${
                  isActive
                    ? "bg-[var(--royal-tint)] text-[var(--royal-hover)]"
                    : "text-[var(--text-2)] hover:bg-[var(--hover)] hover:text-[var(--text)]"
                }`}
              >
                <div className="w-[18px] flex justify-center items-center">
                  <item.icon className={`w-[16px] h-[16px] transition-colors ${isActive ? "text-[var(--royal)]" : "text-[var(--muted-2)] group-hover:text-[var(--royal)]"}`} strokeWidth={1.75} />
                </div>
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* System Section */}
        <div className="text-[11px] text-[var(--muted-2)] uppercase tracking-[0.1em] px-2.5 pt-4 pb-2 font-semibold select-none mt-2">System</div>
        <nav className="flex flex-col">
          {systemItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
            
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-[11px] px-2.5 py-[9px] rounded-[10px] cursor-pointer text-[14px] font-medium transition-all duration-150 ease-out mb-[1px] group select-none ${
                  isActive
                    ? "bg-[var(--royal-tint)] text-[var(--royal-hover)]"
                    : "text-[var(--text-2)] hover:bg-[var(--hover)] hover:text-[var(--text)]"
                }`}
              >
                <div className="w-[18px] flex justify-center items-center">
                  <item.icon className={`w-[16px] h-[16px] transition-colors ${isActive ? "text-[var(--royal)]" : "text-[var(--muted-2)] group-hover:text-[var(--royal)]"}`} strokeWidth={1.75} />
                </div>
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="flex-1"></div>

      {/* User */}
      <div className="px-2.5 pt-3 border-t border-[var(--hairline)] mt-[14px] flex gap-[11px] items-center text-[13px] rounded-[10px] pb-1 select-none">
        <div className="w-[28px] h-[28px] rounded-full bg-gradient-to-br from-[var(--royal)] to-[#6B7CF7] text-white flex items-center justify-center text-[11px] font-semibold shrink-0 shadow-[var(--shadow-xs)]">
          {initials}
        </div>
        <div className="flex flex-col overflow-hidden">
          <div className="font-semibold text-[var(--text)] truncate">Signed in</div>
          <div className="text-[var(--muted)] text-[11.5px] truncate leading-tight">{userEmail}</div>
        </div>
        <button type="button" aria-label="Sign out" title="Sign out" onClick={async () => { await getBrowserAuth().auth.signOut(); window.location.assign("/login"); }} className="ml-auto min-h-11 min-w-11 rounded-lg text-[var(--muted)] hover:bg-[var(--hover)] hover:text-[var(--red)]"><LogOut className="mx-auto h-4 w-4" /></button>
      </div>
    </aside>
  );
}
