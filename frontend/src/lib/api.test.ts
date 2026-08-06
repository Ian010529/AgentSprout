import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, publicApi, studioApi, systemApi } from "./api";

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

describe("API boundary behavior", () => {
  it("preserves Studio credentials, CSRF, and idempotency headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "version-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await studioApi.submitVersion("version-1", "csrf-1", "idempotency-1");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/studio\/versions\/version-1\/submit$/),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: expect.objectContaining({
          "X-CSRF-Token": "csrf-1",
          "Idempotency-Key": "idempotency-1",
        }),
      }),
    );
  });

  it("keeps public polling credential-free and sends only the opaque run token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "run-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await publicApi.getRun("run-1", "opaque-token");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/public\/runs\/run-1$/),
      expect.objectContaining({
        method: "GET",
        credentials: "omit",
        headers: expect.objectContaining({ "X-Public-Run-Token": "opaque-token" }),
      }),
    );
  });
});
