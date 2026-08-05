"use client";

import { useEffect, useState } from "react";

import { ApiError, type ReadinessResponse, systemApi } from "@/lib/api";

type StatusState =
  | { phase: "loading" }
  | { phase: "ready"; data: ReadinessResponse }
  | { phase: "not-ready"; data: ReadinessResponse }
  | { phase: "error"; message: string; requestId: string | null };

function resultState(data: ReadinessResponse): StatusState {
  return { phase: data.status === "ready" ? "ready" : "not-ready", data };
}

function errorState(error: unknown): StatusState {
  const apiError = error instanceof ApiError ? error : null;
  return {
    phase: "error",
    message: apiError?.message ?? "The service check failed.",
    requestId: apiError?.requestId ?? null,
  };
}

export function SystemStatus() {
  const [state, setState] = useState<StatusState>({ phase: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    void systemApi.readiness(controller.signal).then(
      (data) => setState(resultState(data)),
      (error: unknown) => {
        if (!controller.signal.aborted) setState(errorState(error));
      },
    );
    return () => controller.abort();
  }, []);

  async function retry() {
    setState({ phase: "loading" });
    try {
      setState(resultState(await systemApi.readiness()));
    } catch (error) {
      setState(errorState(error));
    }
  }

  if (state.phase === "loading") {
    return (
      <section className="status-card" aria-live="polite" aria-busy="true">
        <span className="status-dot status-dot--checking" aria-hidden="true" />
        <div>
          <p className="eyebrow">Development system</p>
          <h2>Checking the workshop…</h2>
          <p>Confirming SQLite, Chroma, uploads, and migrations.</p>
        </div>
      </section>
    );
  }

  if (state.phase === "error") {
    return (
      <section className="status-card status-card--error" role="status">
        <span className="status-dot status-dot--error" aria-hidden="true" />
        <div>
          <p className="eyebrow">Development system</p>
          <h2>Backend needs attention</h2>
          <p>{state.message}</p>
          {state.requestId ? <p className="request-id">Request ID: {state.requestId}</p> : null}
          <button className="text-button" type="button" onClick={retry}>
            Check again
          </button>
        </div>
      </section>
    );
  }

  const isReady = state.phase === "ready";
  return (
    <section className={`status-card${isReady ? "" : " status-card--error"}`} role="status">
      <span
        className={`status-dot ${isReady ? "status-dot--ready" : "status-dot--error"}`}
        aria-hidden="true"
      />
      <div>
        <p className="eyebrow">Development system</p>
        <h2>{isReady ? "Workshop ready" : "Workshop not ready"}</h2>
        <p>
          {isReady
            ? "Local storage, vector search, uploads, and migrations are available."
            : "One or more local services need attention before the Studio can run."}
        </p>
        <ul className="check-list" aria-label="Readiness checks">
          {Object.entries(state.data.checks).map(([name, result]) => (
            <li key={name}>
              <span>{name}</span>
              <strong>{result}</strong>
            </li>
          ))}
        </ul>
        {!isReady ? (
          <button className="text-button" type="button" onClick={retry}>
            Check again
          </button>
        ) : null}
      </div>
    </section>
  );
}
