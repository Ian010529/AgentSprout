const DEFAULT_API_BASE_URL = "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 8_000;

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
    retryable?: boolean;
    retry_after_seconds?: number | null;
    field_errors?: Record<string, string>;
  };
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly code: string,
    readonly requestId: string | null,
    readonly retryable: boolean,
    readonly retryAfterSeconds: number | null = null,
    readonly fieldErrors: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function apiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ErrorEnvelope = {};
  try {
    body = (await response.json()) as ErrorEnvelope;
  } catch {
    // Normalize non-JSON upstream failures to safe product copy.
  }
  return new ApiError(
    body.error?.message ?? "AgentSprout could not reach the service.",
    response.status,
    body.error?.code ?? "API_ERROR",
    body.error?.request_id ?? response.headers.get("X-Request-ID"),
    body.error?.retryable ?? response.status >= 500,
    body.error?.retry_after_seconds ?? null,
    body.error?.field_errors ?? {},
  );
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  csrfToken?: string;
  idempotencyKey?: string;
  signal?: AbortSignal;
  acceptedStatuses?: readonly number[];
  publicRunToken?: string;
  includeCredentials?: boolean;
};

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const timeoutSignal = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const combinedSignal = options.signal
    ? AbortSignal.any([options.signal, timeoutSignal])
    : timeoutSignal;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.csrfToken) headers["X-CSRF-Token"] = options.csrfToken;
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
  if (options.publicRunToken) headers["X-Public-Run-Token"] = options.publicRunToken;

  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: options.method ?? "GET",
      headers,
      credentials: options.includeCredentials === false ? "omit" : "include",
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: combinedSignal,
    });
    if (!response.ok && !options.acceptedStatuses?.includes(response.status)) {
      throw await parseError(response);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && ["TimeoutError", "AbortError"].includes(error.name)) {
      const abortedByCaller = options.signal?.aborted ?? false;
      throw new ApiError(
        abortedByCaller ? "The request was cancelled." : "The request timed out. Try again.",
        null,
        abortedByCaller ? "CANCELLED" : "TIMEOUT",
        null,
        !abortedByCaller,
      );
    }
    throw new ApiError("The backend is offline or unreachable.", null, "NETWORK_ERROR", null, true);
  }
}

export async function requestForm<T>(
  path: string,
  form: FormData,
  csrfToken: string,
  idempotencyKey: string,
): Promise<T> {
  const timeoutSignal = AbortSignal.timeout(20_000);
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "X-CSRF-Token": csrfToken,
        "Idempotency-Key": idempotencyKey,
      },
      credentials: "include",
      body: form,
      signal: timeoutSignal,
    });
    if (!response.ok) throw await parseError(response);
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && ["TimeoutError", "AbortError"].includes(error.name)) {
      throw new ApiError("The upload timed out. Try again.", null, "TIMEOUT", null, true);
    }
    throw new ApiError("The backend is offline or unreachable.", null, "NETWORK_ERROR", null, true);
  }
}
