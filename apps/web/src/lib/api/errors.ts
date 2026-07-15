export type ApiError = {
  code: string;
  message: string;
  correlation_id: string;
  retryable: boolean;
  user_action: string;
  details: Record<string, unknown>;
};

export async function parseApiError(response: Response): Promise<ApiError> {
  const fallback = { code: "REQUEST_FAILED", message: "The request failed.", correlation_id: response.headers.get("x-correlation-id") ?? "", retryable: false, user_action: "Try again.", details: {} };
  try {
    const body = await response.json();
    return body.error ?? { ...fallback, message: typeof body.detail === "string" ? body.detail : fallback.message };
  } catch {
    return fallback;
  }
}

export class ApiRequestError extends Error {
  constructor(readonly apiError: ApiError) {
    super(apiError.message);
    this.name = "ApiRequestError";
  }
}

export async function requireJson<T>(response: Response): Promise<T> {
  if (!response.ok) throw new ApiRequestError(await parseApiError(response));
  return response.json() as Promise<T>;
}
