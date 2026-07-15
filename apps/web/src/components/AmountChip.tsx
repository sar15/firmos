import React from "react";
import { formatIndianRupee } from "@/lib/formatIndianRupee";

interface AmountChipProps {
  amount: number | string | null | undefined;
  suffix?: string;
  className?: string;
}

export function AmountChip({ amount, suffix, className = "" }: AmountChipProps) {
  if (amount === null || amount === undefined) {
    return null;
  }

  const formattedAmount = formatIndianRupee(amount);

  return (
    <div className={`inline-flex items-center gap-1.5 ${className}`}>
      <span className="font-mono text-right font-medium">
        {formattedAmount}
      </span>
      {suffix && (
        <span className="opacity-70 text-[12px] font-normal whitespace-nowrap">
          {suffix}
        </span>
      )}
    </div>
  );
}
