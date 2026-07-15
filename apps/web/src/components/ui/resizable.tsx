"use client"

import * as React from "react"
import { Group, Panel, Separator } from "react-resizable-panels"

/* ---------- Group wrapper ---------- */
const ResizablePanelGroup = ({
  className,
  direction,
  ...props
}: React.ComponentProps<typeof Group> & { direction?: "horizontal" | "vertical" }) => (
  <Group
    orientation={direction || "horizontal"}
    className={`flex h-full w-full data-[panel-group-direction=vertical]:flex-col ${className || ""}`}
    {...props}
  />
)

/* ---------- Panel (straight pass-through) ---------- */
const ResizablePanel = Panel

/* ---------- Separator wrapper (strips withHandle) ---------- */
const ResizableHandle = ({
  className,
  withHandle,
  ...props
}: React.ComponentProps<typeof Separator> & { withHandle?: boolean }) => (
  <Separator
    className={`relative flex w-2 items-center justify-center bg-transparent after:absolute after:inset-y-0 after:left-1/2 after:w-[1px] after:-translate-x-1/2 after:bg-[var(--hairline)] hover:after:bg-[var(--royal)] data-[resize-handle-state=drag]:after:bg-[var(--royal)] cursor-col-resize outline-none focus-visible:ring-0 ${withHandle ? "before:absolute before:left-1/2 before:top-1/2 before:h-8 before:w-1 before:-translate-x-1/2 before:-translate-y-1/2 before:rounded-full before:bg-[var(--hairline)]" : ""} ${className || ""}`}
    {...props}
  />
)

export { ResizablePanelGroup, ResizablePanel, ResizableHandle }
