"use client";

import React from "react";
import { ApiRequestError } from "@/lib/api/errors";

type ConfirmationPolicy =
  | { kind: "none" }
  | { kind: "confirm"; message: string };

interface ActionButtonProps<Result> {
  capabilityKey: string;
  requiredPermission: string;
  mutation: () => Promise<Result>;
  loadingLabel: string;
  confirmationPolicy: ConfirmationPolicy;
  idempotencyKey?: string;
  correlationId: string;
  successEvidence: (result: Result) => string;
  disabledReason?: string | null;
  onSuccess?: (result: Result) => void;
  className?: string;
  children: React.ReactNode;
}

export function ActionButton<Result>({
  capabilityKey,
  requiredPermission,
  mutation,
  loadingLabel,
  confirmationPolicy,
  idempotencyKey,
  correlationId,
  successEvidence,
  disabledReason,
  onSuccess,
  className,
  children,
}: ActionButtonProps<Result>) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [evidence, setEvidence] = React.useState<string | null>(null);

  const run = async () => {
    if (disabledReason || loading) return;
    if (confirmationPolicy.kind === "confirm" &&
        !window.confirm(confirmationPolicy.message)) return;
    setLoading(true);
    setError(null);
    try {
      const result = await mutation();
      setEvidence(successEvidence(result));
      onSuccess?.(result);
    } catch (caught) {
      const message = caught instanceof ApiRequestError
        ? `${caught.apiError.message} ${caught.apiError.user_action}`.trim()
        : caught instanceof Error ? caught.message : "The action could not be completed.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-w-0">
      <button
        type="button"
        onClick={run}
        disabled={Boolean(disabledReason) || loading}
        title={disabledReason ?? undefined}
        aria-describedby={error ? `${capabilityKey}-error` : undefined}
        data-capability={capabilityKey}
        data-permission={requiredPermission}
        data-idempotency-key={idempotencyKey}
        data-correlation-id={correlationId}
        className={className}
      >
        {loading ? loadingLabel : children}
      </button>
      {disabledReason && (
        <p className="mt-1 max-w-56 text-xs text-[var(--muted)]">{disabledReason}</p>
      )}
      {error && (
        <p id={`${capabilityKey}-error`} role="alert" className="mt-1 max-w-72 text-xs text-[var(--red)]">
          {error}
        </p>
      )}
      {evidence && (
        <p aria-live="polite" className="mt-1 max-w-72 text-xs text-[var(--muted)]">
          {evidence}
        </p>
      )}
    </div>
  );
}
