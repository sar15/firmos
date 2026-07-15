export default function Loading() {
  return (
    <div className="p-8 animate-pulse">
      <div className="h-6 w-48 bg-[var(--hover)] rounded mb-2"></div>
      <div className="h-4 w-64 bg-[var(--hover)] rounded mb-8"></div>
      <div className="h-10 w-full max-w-md bg-[var(--hover)] rounded-[6px] mb-4"></div>
      <div className="h-10 w-full max-w-md bg-[var(--hover)] rounded-[6px] mb-4"></div>
      <div className="h-32 w-full max-w-md bg-[var(--hover)] rounded-[6px]"></div>
    </div>
  );
}
