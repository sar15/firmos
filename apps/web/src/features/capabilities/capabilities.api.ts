import { getAuthHeaders } from "@/lib/auth";

export type CapabilityState =
  | "UNAVAILABLE" | "DISABLED" | "INTERNAL_ONLY" | "CONFIGURATION_REQUIRED"
  | "AVAILABLE" | "DEGRADED" | "BLOCKED_AUTH" | "BLOCKED_MAPPING"
  | "BLOCKED_DEVICE" | "FAILED_CERTIFICATION";

export interface Capability {
  capability_key: string;
  state: CapabilityState;
  implementation_version: string;
  environment: string;
  reason_code: string;
  reason_message: string;
  required_user_action: string;
  last_probe_at: string | null;
  last_success_at: string | null;
  certification_version: string | null;
  certification_level: number;
  feature_flag: string;
}

export async function getCapabilities(): Promise<Capability[]> {
  const response = await fetch("/api/capabilities", { headers: await getAuthHeaders() });
  if (!response.ok) throw new Error("Capability status is unavailable");
  const body = await response.json();
  return body.capabilities;
}
