import { requestJson } from "./client";
import type { HealthResponse, ReadinessResponse } from "./types";

export const systemApi = {
  health: (signal?: AbortSignal) => requestJson<HealthResponse>("/api/v1/health", { signal }),
  readiness: (signal?: AbortSignal) =>
    requestJson<ReadinessResponse>("/api/v1/ready", { signal, acceptedStatuses: [503] }),
};
