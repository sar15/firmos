import { getAuthHeaders } from "@/lib/auth";

export interface FirmMembership {
  id: string;
  name: string;
  role: string;
}

export interface FirmMemberships {
  currentFirmId: string;
  firms: FirmMembership[];
}

export const listFirms = async (): Promise<FirmMemberships> => {
  const response = await fetch("/api/firms", {
    headers: await getAuthHeaders({ includeFirm: false }),
  });
  if (!response.ok) throw new Error("Your firms could not be loaded.");
  return response.json();
};
