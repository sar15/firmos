import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ActionButton } from "./ActionButton";

describe("ActionButton", () => {
  it("binds policy metadata and renders success evidence", async () => {
    const mutation = vi.fn().mockResolvedValue({ id: "action-1" });
    render(
      <ActionButton<{ id: string }>
        capabilityKey="zoho.write.purchase_bill.create"
        requiredPermission="books.approve"
        mutation={mutation}
        loadingLabel="Approving…"
        confirmationPolicy={{ kind: "none" }}
        idempotencyKey="action-1"
        correlationId="corr-1"
        successEvidence={(result) => `Queued ${result.id}`}
      >
        Approve
      </ActionButton>
    );

    const button = screen.getByRole("button", { name: "Approve" });
    expect(button).toHaveAttribute("data-capability", "zoho.write.purchase_bill.create");
    expect(button).toHaveAttribute("data-permission", "books.approve");
    fireEvent.click(button);
    expect(await screen.findByText("Queued action-1")).toBeVisible();
    expect(mutation).toHaveBeenCalledOnce();
  });

  it("explains why an unsupported action is disabled", () => {
    render(
      <ActionButton
        capabilityKey="billing.manage"
        requiredPermission="billing.manage"
        mutation={vi.fn()}
        loadingLabel="Saving…"
        confirmationPolicy={{ kind: "none" }}
        correlationId="corr-2"
        successEvidence={() => "Saved"}
        disabledReason="Billing entitlements are not enforced yet"
      >
        Save
      </ActionButton>
    );
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(screen.getByText("Billing entitlements are not enforced yet")).toBeVisible();
  });
});
