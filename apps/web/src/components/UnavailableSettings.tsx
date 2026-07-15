interface UnavailableSettingsProps {
  title: string;
  description: string;
}

export function UnavailableSettings({ title, description }: UnavailableSettingsProps) {
  return (
    <section className="max-w-2xl p-8">
      <h2 className="text-lg font-semibold text-[var(--text)]">{title}</h2>
      <div className="mt-6 rounded-[6px] border border-[var(--hairline)] bg-white p-5 text-sm text-[var(--muted)]">
        {description}
      </div>
    </section>
  );
}
