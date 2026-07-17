import { describe, expect, it } from "vitest";
import { ReconMatchSchema } from "./index";

const portalEntry = {
  id: "gstr2b-1",
  date: "2026-06-12",
  description: "GSTR-2B document",
  counterparty: "27ABCDE1234F1Z5",
  amount: 125000,
};

describe("ReconMatchSchema", () => {
  it("accepts a portal-only GSTR-2B record without fabricating a books record", () => {
    const result = ReconMatchSchema.safeParse({
      id: "match-1",
      status: "UNMATCHED",
      source: null,
      target: portalEntry,
      flag: "PORTAL_ENTRY_NOT_IN_BOOKS",
    });

    expect(result.success).toBe(true);
  });

  it("rejects a match with neither a books nor portal record", () => {
    const result = ReconMatchSchema.safeParse({
      id: "match-1",
      status: "UNMATCHED",
      source: null,
      target: null,
    });

    expect(result.success).toBe(false);
  });
});
