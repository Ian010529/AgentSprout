const DEFAULT_API_BASE_URL = "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 5_000;

export type HealthResponse = {
  status: "ok";
  service: "agentsprout-api";
};

export type ReadinessCheck = "ok" | "failed";

export type ReadinessResponse = {
  status: "ready" | "not_ready";
  checks: Record<"sqlite" | "chroma" | "uploads" | "migrations", ReadinessCheck>;
};

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
    retryable?: boolean;
  };
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly code: string,
    readonly requestId: string | null,
    readonly retryable: boolean,
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
    // Non-JSON upstream failures are normalized to safe copy below.
  }

  const requestId = body.error?.request_id ?? response.headers.get("X-Request-ID");
  const message = body.error?.message ?? "AgentSprout could not reach the service.";
  return new ApiError(
    message,
    response.status,
    body.error?.code ?? "API_ERROR",
    requestId,
    body.error?.retryable ?? response.status >= 500,
  );
}

async function getJson<T>(
  path: string,
  signal?: AbortSignal,
  acceptedStatuses: readonly number[] = [],
): Promise<T> {
  const timeoutSignal = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const combinedSignal = signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal;

  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "include",
      signal: combinedSignal,
    });
    if (!response.ok && !acceptedStatuses.includes(response.status)) {
      throw await parseError(response);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError("The service check timed out. Try again.", null, "TIMEOUT", null, true);
    }
    throw new ApiError("The backend is offline or unreachable.", null, "NETWORK_ERROR", null, true);
  }
}

export const systemApi = {
  health: (signal?: AbortSignal) => getJson<HealthResponse>("/api/v1/health", signal),
  readiness: (signal?: AbortSignal) =>
    getJson<ReadinessResponse>("/api/v1/ready", signal, [503]),
};
