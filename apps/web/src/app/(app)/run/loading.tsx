export default function Loading() {
  return (
    <div className="flex-1 w-full h-full flex items-center justify-center bg-[var(--canvas)]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-5 h-5 border-2 border-[var(--royal)] border-t-transparent rounded-full animate-spin" />
        <span className="text-[13px] font-medium text-[var(--muted)] animate-pulse">Loading...</span>
      </div>
    </div>
  );
}
