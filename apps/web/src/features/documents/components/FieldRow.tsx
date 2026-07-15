import React, { useRef, useEffect, useState } from "react";
import { ExtractedField } from "@/types";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { cn } from "@/lib/utils";
import { AlertCircle, ChevronDown } from "lucide-react";
import { formatIndianRupee } from "@/lib/formatIndianRupee";

const EXPENSE_HEADS = [
  "General Expenses",
  "Software & Cloud Services",
  "Travel & Accommodation",
  "Meals & Entertainment",
  "Office Supplies",
  "Legal & Professional Fees",
  "Advertising & Marketing",
  "Rent & Utilities",
  "Cost of Goods Sold"
];

interface FieldRowProps {
  field: ExtractedField;
  onUpdate: (key: string, value: string) => void;
  onFocus: (key: string) => void;
  onBlur: () => void;
  isFocused?: boolean;
}

export function FieldRow({ field, onUpdate, onFocus, onBlur, isFocused }: FieldRowProps) {
  const [value, setValue] = useState(field.value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setValue(field.value);
  }, [field.value]);

  useEffect(() => {
    if (isFocused && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isFocused]);

  const handleBlur = () => {
    if (value !== field.value) {
      onUpdate(field.key, value);
    }
    onBlur();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      inputRef.current?.blur();
    }
  };

  const needsReview = field.level === "LOW" || field.level === "REVIEW";
  const isAmount = field.key.toLowerCase().includes("amount") || field.key.toLowerCase().includes("total") || field.key.toLowerCase().includes("gst");
  const isTotal = field.key === "total";

  const displayValue = (isAmount && !isNaN(Number(value)) && !isFocused && value.trim() !== "")
    ? formatIndianRupee(Number(value) * 100)
    : value;

  return (
    <div
      className={cn(
        "flex flex-col p-4 border-b border-[var(--hairline)] transition-colors duration-200",
        isFocused ? "bg-[var(--hover)] relative z-10" : "bg-white",
        needsReview ? "border-l-2 border-l-[var(--amber)] pl-[14px]" : ""
      )}
      onMouseEnter={() => onFocus(field.key)}
      onMouseLeave={onBlur}
    >
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
          {field.label}
        </label>
        <div className="flex items-center gap-2">
          {needsReview && (
            <span className="text-[10px] text-amber font-medium flex items-center gap-1">
              <AlertCircle className="h-3 w-3" />
              Verify
            </span>
          )}
          <ConfidenceBadge level={field.level} />
        </div>
      </div>

      <div className="flex items-center w-full relative">
        {field.key === "expenseHead" ? (
          <div className="w-full relative">
            <select
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                onUpdate(field.key, e.target.value);
              }}
              onFocus={() => onFocus(field.key)}
              onBlur={onBlur}
              className="w-full appearance-none bg-slate-50 border border-slate-200 focus:bg-white focus:border-[var(--royal)] focus:ring-1 focus:ring-[var(--royal)] rounded-md px-3 py-2 text-[14px] text-slate-900 font-medium transition-all outline-none shadow-sm pr-8"
            >
              <option value="" disabled>Select expense head...</option>
              {EXPENSE_HEADS.map(head => (
                <option key={head} value={head}>{head}</option>
              ))}
              {value && !EXPENSE_HEADS.includes(value) && (
                <option value={value}>{value}</option>
              )}
            </select>
            <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        ) : (
          <input
            ref={inputRef}
            type="text"
            value={displayValue}
            onChange={(e) => setValue(e.target.value)}
            onFocus={() => onFocus(field.key)}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            className={cn(
              "w-full bg-slate-50 border border-slate-200 focus:bg-white focus:border-[var(--royal)] focus:ring-1 focus:ring-[var(--royal)] rounded-md px-3 py-2 text-[14px] transition-all outline-none shadow-sm",
              isAmount || field.key.toLowerCase().includes("gstin") || field.key.toLowerCase().includes("date")
                ? "font-mono tabular-nums text-slate-900" 
                : "text-slate-900 font-medium",
              isTotal && !isFocused ? "font-bold text-[15px]" : ""
            )}
            placeholder={`Enter ${field.label.toLowerCase()}...`}
          />
        )}
      </div>
    </div>
  );
}
