import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, systemApi } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("systemApi", () => {
  it("returns the typed readiness contract", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: "ready",
            checks: { sqlite: "ok", chroma: "ok", uploads: "ok", migrations: "ok" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(systemApi.readiness()).resolves.toMatchObject({ status: "ready" });
  });

  it("normalizes safe API errors and preserves request IDs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "SERVICE_NOT_READY",
              message: "The service is not ready.",
              request_id: "request-123",
              retryable: true,
            },
          }),
          { status: 503, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    const error = await systemApi.health().catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 503, code: "SERVICE_NOT_READY", requestId: "request-123" });
  });

  it("returns failed readiness checks from the contracted 503 response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: "not_ready",
            checks: { sqlite: "ok", chroma: "failed", uploads: "ok", migrations: "ok" },
          }),
          { status: 503, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(systemApi.readiness()).resolves.toMatchObject({
      status: "not_ready",
      checks: { chroma: "failed" },
    });
  });
});
