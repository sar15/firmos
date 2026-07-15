export default function Loading() {
  return (
    <div className="flex flex-col h-full bg-[var(--canvas)] animate-pulse">
      <div className="h-[64px] border-b border-[var(--hairline)] px-6 flex items-center">
        <div className="h-5 w-48 bg-[var(--hover)] rounded"></div>
      </div>
      <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 flex flex-col gap-6">
          <div className="h-64 bg-white border border-[var(--hairline)] rounded-[6px]"></div>
          <div className="h-64 bg-white border border-[var(--hairline)] rounded-[6px]"></div>
        </div>
        <div className="flex flex-col gap-6">
          <div className="h-48 bg-white border border-[var(--hairline)] rounded-[6px]"></div>
          <div className="h-48 bg-white border border-[var(--hairline)] rounded-[6px]"></div>
        </div>
      </div>
    </div>
  );
}
