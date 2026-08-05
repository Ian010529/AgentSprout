"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useRef, useState } from "react";

import { ApiError, studioApi } from "@/lib/api";

function accessError(error: unknown): string {
  if (!(error instanceof ApiError)) return "The Studio could not open. Try again.";
  if (error.code === "ACCESS_DENIED") return "That access code was not recognized.";
  if (error.status === 429) {
    const wait = error.retryAfterSeconds ? ` Try again in about ${error.retryAfterSeconds} seconds.` : "";
    return `Too many attempts.${wait}`;
  }
  if (error.code === "TIMEOUT") return "The Studio took too long to respond. Try again.";
  if (error.code === "NETWORK_ERROR") return "The Studio service is offline or unreachable.";
  return error.message;
}

export function AccessForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const inputRef = useRef<HTMLInputElement>(null);
  const [code, setCode] = useState("");
  const [showCode, setShowCode] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const expired = searchParams.get("reason") === "expired";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!code.trim() || pending) return;
    setPending(true);
    setError(null);
    try {
      await studioApi.access(code);
      setCode("");
      router.replace("/studio");
    } catch (reason) {
      setError(accessError(reason));
      inputRef.current?.focus();
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="access-panel" aria-label="Studio access">
      <div className="access-panel-index" aria-hidden="true">
        01 / ENTRY
      </div>
      <div>
        <p className="eyebrow">Expedition desk</p>
        <h2>Enter your Studio code</h2>
        <p className="form-help">The code is sent only to the Studio API and is never saved here.</p>
      </div>
      {expired ? (
        <p className="form-notice" role="status">
          Your previous Studio session ended. Enter the code to continue.
        </p>
      ) : null}
      <form onSubmit={submit} noValidate>
        <label htmlFor="access-code">Access code</label>
        <div className="secret-field">
          <input
            ref={inputRef}
            id="access-code"
            name="access-code"
            type={showCode ? "text" : "password"}
            autoComplete="off"
            value={code}
            disabled={pending}
            aria-invalid={error ? "true" : "false"}
            aria-describedby={error ? "access-error" : "access-help"}
            onChange={(event) => setCode(event.target.value)}
            required
          />
          <button type="button" onClick={() => setShowCode((value) => !value)} disabled={pending}>
            {showCode ? "Hide" : "Show"}
          </button>
        </div>
        <p id="access-help" className="field-hint">
          Ask the demo host if you do not have the current code.
        </p>
        {error ? (
          <p id="access-error" className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <button className="studio-primary" type="submit" disabled={pending || !code.trim()}>
          {pending ? "Opening Studio…" : "Enter Studio"}
        </button>
      </form>
      <Link className="panel-back-link" href="/">
        ← Return to the concept
      </Link>
    </section>
  );
}
