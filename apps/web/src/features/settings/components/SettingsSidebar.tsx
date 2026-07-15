"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { User, Users, CreditCard, Shield } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { label: "Profile", href: "/settings/profile", icon: User },
  { label: "Team", href: "/settings/team", icon: Users },
  { label: "Billing", href: "/settings/billing", icon: CreditCard },
  { label: "Security", href: "/settings/security", icon: Shield },
];

export function SettingsSidebar() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-1 p-4">
      {NAV_ITEMS.map((item) => {
        const isActive = pathname.startsWith(item.href);
        const Icon = item.icon;
        
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-[6px] text-[13px] font-medium transition-colors",
              isActive 
                ? "bg-[var(--royal)]/10 text-[var(--royal)]" 
                : "text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--hover)]"
            )}
          >
            <Icon className="w-[16px] h-[16px]" strokeWidth={isActive ? 2 : 1.5} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
