import React, { useRef, useState, useMemo } from "react";
import { ReconMatch } from "@/types";
import { MatchRow } from "./MatchRow";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronDown, ChevronRight, CheckCircle2 } from "lucide-react";
import { formatIndianRupee } from "@/lib/formatIndianRupee";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/EmptyState";

interface MatchPaneProps {
  suggested: ReconMatch[];
  unmatched: ReconMatch[];
  matched: ReconMatch[];
  focusedId: string | null;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onUndo: (id: string) => void;
}

type ListItem = 
  | { type: "header", bucket: "suggested" | "unmatched" | "autoMatched", id: string }
  | { type: "match", match: ReconMatch, id: string };

export function MatchPane({
  suggested,
  unmatched,
  matched,
  focusedId,
  onAccept,
  onReject,
  onUndo,
}: MatchPaneProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  
  const [collapsed, setCollapsed] = useState({
    suggested: false,
    unmatched: false,
    autoMatched: true,
  });

  const toggleCollapse = (bucket: keyof typeof collapsed) => {
    setCollapsed(prev => ({ ...prev, [bucket]: !prev[bucket] }));
  };

  const activeItems = useMemo(() => {
    const items: ListItem[] = [];
    
    items.push({ type: "header", bucket: "suggested", id: "h-suggested" });
    if (!collapsed.suggested) {
      items.push(...suggested.map(m => ({ type: "match" as const, match: m, id: m.id })));
    }

    items.push({ type: "header", bucket: "unmatched", id: "h-unmatched" });
    if (!collapsed.unmatched) {
      items.push(...unmatched.map(m => ({ type: "match" as const, match: m, id: m.id })));
    }

    items.push({ type: "header", bucket: "autoMatched", id: "h-autoMatched" });
    if (!collapsed.autoMatched) {
      items.push(...matched.map(m => ({ type: "match" as const, match: m, id: m.id })));
    }

    return items;
  }, [suggested, unmatched, matched, collapsed]);

  // TanStack Virtual intentionally exposes mutable measurement callbacks.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: activeItems.length,
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => activeItems[index].type === "header" ? 44 : 96,
    overscan: 10,
  });

  const renderHeader = (bucket: "suggested" | "unmatched" | "autoMatched") => {
    const isCollapsed = collapsed[bucket];
    let label = "";
    let dotColor = "";
    let count = 0;
    let sum = 0;
    
    if (bucket === "suggested") {
      label = "Needs review";
      dotColor = "bg-[var(--amber)]";
      count = suggested.length;
      sum = suggested.reduce((acc, m) => acc + (m.source?.amount ?? m.target?.amount ?? 0), 0);
    } else if (bucket === "unmatched") {
      label = "Unmatched";
      dotColor = "bg-[var(--red)]";
      count = unmatched.length;
      sum = unmatched.reduce((acc, m) => acc + (m.source?.amount ?? m.target?.amount ?? 0), 0);
    } else {
      label = "Auto-matched";
      dotColor = "bg-[var(--royal)]";
      count = matched.length;
      sum = matched.reduce((acc, m) => acc + (m.source?.amount ?? m.target?.amount ?? 0), 0);
    }

    return (
      <button 
        className="w-full flex items-center gap-3 px-4 py-3 bg-[var(--canvas)] border-b border-[var(--hairline)] hover:bg-[var(--hover)] transition-colors text-left font-medium z-20 focus-ring"
        onClick={() => toggleCollapse(bucket)}
      >
        {isCollapsed ? <ChevronRight className="h-4 w-4 text-[var(--muted)]" /> : <ChevronDown className="h-4 w-4 text-[var(--muted)]" />}
        <div className="flex items-center gap-2">
          <div className={cn("w-2 h-2 rounded-full", dotColor)} />
          <span className="text-[var(--text)] text-[13px]">{label}</span>
          <span className="text-[var(--muted)]">·</span>
          <span className="text-[var(--text)] font-mono text-[13px]">{count}</span>
          <span className="text-[var(--muted)]">·</span>
          <span className="text-[var(--text)] font-mono text-[13px] tabular-nums">{formatIndianRupee(sum)}</span>
        </div>
      </button>
    );
  };

  const activeStickyIndex = virtualizer.getVirtualItems().length > 0
    ? (() => {
        const topIndex = virtualizer.getVirtualItems()[0].index;
        for (let i = topIndex; i >= 0; i--) {
          if (activeItems[i].type === "header") return i;
        }
        return null;
      })()
    : null;

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[var(--canvas)] relative">
      {suggested.length === 0 && unmatched.length === 0 && matched.length === 0 ? (
        <div className="p-8 h-full flex items-center justify-center">
          <EmptyState 
            icon={CheckCircle2} 
            title="All caught up" 
            description="There are no remaining entries to reconcile for this period." 
          />
        </div>
      ) : (
        <div 
          ref={parentRef}
          className="flex-1 overflow-y-auto relative"
        >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {virtualizer.getVirtualItems().map((virtualItem) => {
            const item = activeItems[virtualItem.index];
            return (
              <div
                key={virtualItem.key}
                ref={virtualizer.measureElement}
                data-index={virtualItem.index}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualItem.size}px`,
                  transform: `translateY(${virtualItem.start}px)`,
                }}
              >
                {item.type === "header" ? (
                  renderHeader(item.bucket)
                ) : (
                  <MatchRow
                    match={item.match}
                    isFocused={focusedId === item.match.id}
                    onAccept={onAccept}
                    onReject={onReject}
                    onUndo={onUndo}
                  />
                )}
              </div>
            );
          })}
        </div>
        
        {activeStickyIndex !== null && (
          <div className="sticky top-0 left-0 w-full z-30">
            {renderHeader((activeItems[activeStickyIndex] as Extract<ListItem, { type: "header" }>).bucket)}
          </div>
        )}
      </div>
      )}
    </div>
  );
}
