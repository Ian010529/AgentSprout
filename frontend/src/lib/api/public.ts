import { requestJson } from "./client";
import type { ChatPhase, PublicAgent, PublicRun } from "./types";

export const publicApi = {
  getAgent: (slug: string, signal?: AbortSignal) =>
    requestJson<PublicAgent>(`/api/v1/public/agents/${encodeURIComponent(slug)}`, {
      signal,
      includeCredentials: false,
    }),
  startRun: (slug: string, message: string, idempotencyKey: string) =>
    requestJson<{ run_id: string; run_token: string; phase: ChatPhase; poll_after_ms: number }>(
      `/api/v1/public/agents/${encodeURIComponent(slug)}/runs`,
      { method: "POST", body: { message }, idempotencyKey, includeCredentials: false },
    ),
  getRun: (runId: string, runToken: string, signal?: AbortSignal) =>
    requestJson<PublicRun>(`/api/v1/public/runs/${runId}`, {
      signal,
      publicRunToken: runToken,
      includeCredentials: false,
    }),
};
