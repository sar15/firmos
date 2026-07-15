import { TopBar } from "./TopBar";
import { LeftRail } from "./LeftRail";
import { CommandPalette } from "./CommandPalette";
import { ContextColumn } from "@/features/context/ContextColumn";

interface AppShellProps {
  children: React.ReactNode;
  userEmail: string;
}

export function AppShell({ children, userEmail }: AppShellProps) {
  return (
    <>
      <div className="md:hidden flex flex-col h-[100dvh] w-screen items-center justify-center p-8 bg-[var(--canvas)] text-center">
        <div className="w-12 h-12 bg-[var(--royal)] rounded-[8px] flex items-center justify-center text-white font-bold text-xl mb-4">
          f
        </div>
        <h2 className="text-[15px] font-semibold text-[var(--text)] mb-1.5">firmOS is best on desktop</h2>
        <p className="text-[13px] text-[var(--muted)] max-w-[280px]">
          Our command center is designed for larger screens. Please open firmOS on a computer.
        </p>
      </div>

      <div className="hidden md:flex h-screen w-screen bg-[var(--canvas)] text-[var(--text)] overflow-hidden antialiased">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-white focus:text-[var(--royal)]">
          Skip to content
        </a>
        <LeftRail userEmail={userEmail} />
        <div className="flex flex-col flex-1 min-w-0">
          <TopBar />
          <main id="main" className="flex-1 overflow-y-auto bg-[var(--canvas)] flex flex-col min-h-0 relative">
            {children}
          </main>
        </div>
        <ContextColumn />
        <CommandPalette />
      </div>
    </>
  );
}
