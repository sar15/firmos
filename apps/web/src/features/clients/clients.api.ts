import { Client, Decision, ExtractedDocument } from "@/types";
import { getAuthHeaders } from "@/lib/auth";
export interface ListClientsFilter {
  entityType?: "PRIVATE_LIMITED" | "LLP" | "PROPRIETOR" | "PARTNERSHIP" | string;
  status?: "ON_TRACK" | "DUE_SOON" | "OVERDUE" | string;
  booksProvider?: "ZOHO_BOOKS" | "TALLY" | "QUICKBOOKS" | "CSV" | "NONE" | null | string;
  search?: string;
}

export interface SearchResults {
  clients: Client[];
  decisions: Decision[];
  documents: ExtractedDocument[];
}

/**
 * Returns a filtered list of clients from the backend.
 */
export async function listClients(filter?: ListClientsFilter): Promise<Client[]> {
  const params = new URLSearchParams();
  if (filter?.entityType) params.append("entityType", filter.entityType);
  if (filter?.status) params.append("status", filter.status);
  if (filter?.booksProvider !== undefined && filter?.booksProvider !== null) {
    params.append("booksProvider", filter.booksProvider);
  }
  if (filter?.search) params.append("search", filter.search);

  const res = await fetch(`/api/clients?${params.toString()}`, {
    headers: await getAuthHeaders(),
  });
  
  if (!res.ok) {
    throw new Error(`Failed to list clients: ${res.statusText}`);
  }
  
  return res.json();
}

/**
 * Returns a single client by ID.
 */
export async function getClient(id: string): Promise<Client> {
  const res = await fetch(`/api/clients/${id}`, {
    headers: await getAuthHeaders(),
  });
  
  if (!res.ok) {
    throw new Error(`Failed to get client: ${res.statusText}`);
  }
  
  return res.json();
}

/**
 * Performs a grouped search across clients, decisions, and documents via the backend.
 */
export async function searchEverything(q: string): Promise<SearchResults> {
  if (!q.trim()) {
    return {
      clients: [],
      decisions: [],
      documents: [],
    };
  }

  const res = await fetch(`/api/clients/search?q=${encodeURIComponent(q)}`, {
    headers: await getAuthHeaders(),
  });
  
  if (!res.ok) {
    throw new Error(`Failed to search: ${res.statusText}`);
  }
  
  return res.json();
}

export type ClientCreateParams = {
  legalName: string;
  pan: string;
  gstin?: string;
  entityType?: string;
  state?: string;
  booksProvider?: string;
};

export async function createClient(data: ClientCreateParams): Promise<Client> {
  const res = await fetch(`/api/clients`, {
    method: "POST",
    headers: await getAuthHeaders(),
    body: JSON.stringify(data),
  });
  
  if (!res.ok) {
    throw new Error(`Failed to create client: ${res.statusText}`);
  }
  
  return res.json();
}

export async function updateClient(id: string, data: ClientCreateParams): Promise<Client> {
  const res = await fetch(`/api/clients/${id}`, {
    method: "PUT",
    headers: await getAuthHeaders(),
    body: JSON.stringify(data),
  });
  
  if (!res.ok) {
    throw new Error(`Failed to update client: ${res.statusText}`);
  }
  
  return res.json();
}

export async function deleteClient(id: string): Promise<void> {
  const res = await fetch(`/api/clients/${id}`, {
    method: "DELETE",
    headers: await getAuthHeaders(),
  });
  
  if (!res.ok) {
    throw new Error(`Failed to delete client: ${res.statusText}`);
  }
}

export interface ClientProfile {
  client: Client;
  recentDocuments: {
    id: string;
    fileUrl: string;
    docKind: string;
    status: string;
    uploadedAt: string;
  }[];
  recentDecisions: {
    id: string;
    task: string;
    status: string;
    amount: number;
    createdAt: string;
  }[];
}

export async function getClientProfile(id: string): Promise<ClientProfile> {
  const res = await fetch(`/api/clients/${id}/profile`, {
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to get client profile: ${res.statusText}`);
  return res.json();
}
