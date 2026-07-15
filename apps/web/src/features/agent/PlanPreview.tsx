import { AgentAction } from "./agent.api";
import { formatIndianRupee } from "@/lib/formatIndianRupee";

export function PlanPreview({ action }: { action: AgentAction }) {
  const step = action.plan_step;
  const diff = action.financial_diff;
  const taxes = Object.entries(diff.taxes);

  return (
    <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
      <section className="rounded-lg border border-[var(--hairline)] bg-[var(--panel)] p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Plan preview</p>
        <dl className="mt-2 grid gap-2">
          <Row label="Reads" value={step.input_source_ids.length ? step.input_source_ids.join(", ") : "No source evidence linked"} />
          <Row label="Prepares" value={step.expected_output} />
          <Row label="Approval" value={step.approval_policy.replaceAll("_", " ").toLowerCase()} />
          <Row label="Recovery" value={step.rollback_recovery} />
        </dl>
      </section>
      <section className="rounded-lg border border-[var(--hairline)] bg-[var(--panel)] p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Financial diff · new object</p>
        <dl className="mt-2 grid gap-2">
          {Object.entries(diff.after).slice(0, 5).map(([key, value]) => (
            <Row key={key} label={key.replaceAll("_", " ")} value={moneyValue(key, value)} />
          ))}
          {taxes.length > 0 && <Row label="Tax components" value={taxes.map(([key, value]) => `${key.replace("_paise", "").toUpperCase()} ${formatIndianRupee(Number(value))}`).join(" · ")} />}
          {diff.total_paise != null && <Row label="Total" value={formatIndianRupee(diff.total_paise)} strong />}
        </dl>
      </section>
    </div>
  );
}

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return <div><dt className="text-xs capitalize text-[var(--muted)]">{label}</dt><dd className={strong ? "font-mono font-semibold text-[var(--text)]" : "text-[var(--text-2)]"}>{value}</dd></div>;
}

function moneyValue(key: string, value: unknown) {
  if (key.endsWith("_paise") && typeof value === "number") return formatIndianRupee(value);
  return String(value);
}
