"use client";

import { ChangeEvent, DragEvent, useEffect, useId, useRef, useState } from "react";

import {
  ApiError,
  type IngestionJob,
  type IngestionState,
  type Role,
  type VersionDetail,
  studioApi,
} from "@/lib/api";

const MAX_FILE_BYTES = 15 * 1024 * 1024;
const ACTIVE_STATES = new Set<IngestionState>([
  "UPLOADED",
  "EXTRACTING",
  "CHUNKING",
  "EMBEDDING",
]);
const STAGES: { state: Exclude<IngestionState, "FAILED">; label: string; note: string }[] = [
  { state: "UPLOADED", label: "Uploaded", note: "Stored in the private workspace" },
  { state: "EXTRACTING", label: "Extracting", note: "Reading page-aware text" },
  { state: "CHUNKING", label: "Chunking", note: "Building stable evidence passages" },
  { state: "EMBEDDING", label: "Embedding", note: "Indexing with OpenAI + Chroma" },
  { state: "READY", label: "Ready", note: "Available for grounded testing" },
];

type KnowledgePanelProps = {
  role: Role;
  csrf: string;
  version: VersionDetail;
  onVersionChange: (version: VersionDetail) => void;
  onSessionExpired: () => void;
};

function fileProblem(file: File): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!extension || !["pdf", "txt", "md"].includes(extension)) {
    return "Choose one PDF, TXT, or Markdown file.";
  }
  if (file.size === 0) return "That file is empty.";
  if (file.size > MAX_FILE_BYTES) return "Files must be 15 MB or smaller.";
  return null;
}

function optimisticJob(response: {
  job_id: string;
  document_id: string;
  state: IngestionState;
}): IngestionJob {
  return {
    id: response.job_id,
    document_id: response.document_id,
    state: response.state,
    progress: { completed: 0, total: 0 },
    safe_error: null,
    error_code: null,
    retryable: false,
    updated_at: new Date().toISOString(),
  };
}

export function KnowledgePanel({
  role,
  csrf,
  version,
  onVersionChange,
  onSessionExpired,
}: KnowledgePanelProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<File | null>(null);
  const [job, setJob] = useState<IngestionJob | null>(version.knowledge.latest_job);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const jobId = job?.id;
  const jobState = job?.state;
  useEffect(() => {
    if (!jobId || !jobState || !ACTIVE_STATES.has(jobState)) return;
    const activeJobId = jobId;
    const controller = new AbortController();
    let timer = 0;

    async function poll() {
      try {
        const latest = await studioApi.getIngestionJob(activeJobId, controller.signal);
        if (ACTIVE_STATES.has(latest.state)) {
          setJob(latest);
          timer = window.setTimeout(() => void poll(), 550);
          return;
        }
        const refreshed = await studioApi.getVersion(version.id);
        setJob(latest);
        onVersionChange(refreshed);
      } catch (error) {
        if (error instanceof ApiError && error.code === "CANCELLED") return;
        if (error instanceof ApiError && error.status === 401) return onSessionExpired();
        setNotice(error instanceof Error ? error.message : "Processing status could not refresh.");
        timer = window.setTimeout(() => void poll(), 1_500);
      }
    }

    timer = window.setTimeout(() => void poll(), 250);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [jobId, jobState, onSessionExpired, onVersionChange, version.id]);

  const editable = role === "STUDENT" && version.allowed_actions.includes("EDIT_DRAFT");
  const processing = Boolean(job && ACTIVE_STATES.has(job.state));
  const activeDocument = version.knowledge.active_document;
  const failedReplacement = Boolean(
    job?.state === "FAILED" && activeDocument && job.document_id !== activeDocument.id,
  );

  function choose(file: File | null) {
    setNotice(null);
    if (!file) return setSelected(null);
    const problem = fileProblem(file);
    if (problem) {
      setSelected(null);
      setNotice(problem);
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setSelected(file);
  }

  function handleInput(event: ChangeEvent<HTMLInputElement>) {
    choose(event.target.files?.[0] ?? null);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!editable || processing || busy) return;
    choose(event.dataTransfer.files?.[0] ?? null);
  }

  async function refreshVersion() {
    const refreshed = await studioApi.getVersion(version.id);
    onVersionChange(refreshed);
    setJob(refreshed.knowledge.latest_job);
  }

  async function upload() {
    if (!selected || !editable || processing || busy) return;
    setBusy(true);
    setNotice(null);
    try {
      const response = await studioApi.uploadKnowledge(
        version.id,
        selected,
        csrf,
        `upload-${Date.now()}-${selected.name}`,
      );
      setJob(optimisticJob(response));
      setSelected(null);
      if (inputRef.current) inputRef.current.value = "";
      await refreshVersion();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onSessionExpired();
      else setNotice(error instanceof Error ? error.message : "The file could not be uploaded.");
    } finally {
      setBusy(false);
    }
  }

  async function retry() {
    if (!job || !job.retryable || !editable || busy) return;
    setBusy(true);
    setNotice(null);
    try {
      const response = await studioApi.retryIngestion(job.id, csrf);
      setJob(optimisticJob(response));
      await refreshVersion();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onSessionExpired();
      else setNotice(error instanceof Error ? error.message : "The upload could not be retried.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    const documentId = job?.state === "FAILED" ? job.document_id : activeDocument?.id;
    if (!documentId || !editable || processing || busy) return;
    setBusy(true);
    setNotice(null);
    try {
      await studioApi.deleteKnowledge(version.id, documentId, csrf);
      if (job?.document_id === documentId) setJob(null);
      await refreshVersion();
      setNotice("The source and its indexed passages were removed.");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onSessionExpired();
      else setNotice(error instanceof Error ? error.message : "The source could not be removed.");
    } finally {
      setBusy(false);
    }
  }

  const currentIndex = job?.state === "FAILED" ? -1 : STAGES.findIndex((item) => item.state === job?.state);
  const progress = job?.progress;

  return (
    <section className="knowledge-sheet" aria-labelledby="knowledge-title">
      <div className="knowledge-intro">
        <p className="eyebrow">02 · Knowledge</p>
        <h2 id="knowledge-title">Give the Agent one trusted field guide.</h2>
        <p>
          AgentSprout extracts real page text, creates stable evidence passages, and indexes them
          for exact-version retrieval. Original files stay private.
        </p>
        <dl className="knowledge-constraints">
          <div><dt>Formats</dt><dd>PDF · TXT · MD</dd></div>
          <div><dt>Limit</dt><dd>15 MB · 100 pages</dd></div>
          <div><dt>OCR</dt><dd>Not included</dd></div>
        </dl>
        {role === "TEACHER" ? (
          <p className="read-only-note">Teacher view shows evidence status but cannot replace it.</p>
        ) : null}
      </div>

      <div className="knowledge-workbench">
        <div
          className={`knowledge-dropzone${dragging ? " is-dragging" : ""}${!editable ? " is-disabled" : ""}`}
          onDragEnter={(event) => {
            event.preventDefault();
            if (editable && !processing) setDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
          }}
          onDrop={handleDrop}
        >
          <span className="source-glyph" aria-hidden="true">↥</span>
          <div>
            <strong>{selected ? selected.name : activeDocument ? "Replace the current source" : "Drop a trusted source here"}</strong>
            <p>{selected ? `${(selected.size / 1024).toFixed(1)} KB selected` : "or choose a file from this device"}</p>
          </div>
          <label className="file-button" htmlFor={inputId} aria-disabled={!editable || processing || busy}>
            Choose file
          </label>
          <input
            ref={inputRef}
            id={inputId}
            className="visually-hidden"
            type="file"
            accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
            disabled={!editable || processing || busy}
            onChange={handleInput}
          />
        </div>

        {selected ? (
          <div className="upload-commit">
            <span>Nothing is processed until you confirm.</span>
            <button type="button" className="studio-primary" disabled={busy} onClick={() => void upload()}>
              {busy ? "Uploading…" : activeDocument ? "Replace source" : "Use this source"}
            </button>
          </div>
        ) : null}

        {activeDocument ? (
          <article className="source-record">
            <div className="source-record-mark" aria-hidden="true">{activeDocument.original_filename.endsWith(".pdf") ? "PDF" : "TXT"}</div>
            <div>
              <p className="eyebrow">Active evidence source</p>
              <h3>{activeDocument.original_filename}</h3>
              <p>{activeDocument.page_count ?? 1} pages · {activeDocument.chunk_count ?? 0} passages · {activeDocument.embedding_model}</p>
            </div>
            <span className="source-ready">Ready</span>
          </article>
        ) : null}

        {job ? (
          <div className={`ingestion-card ingestion-card--${job.state.toLowerCase()}`} aria-live="polite">
            <div className="ingestion-heading">
              <div><p className="eyebrow">Ingestion run</p><h3>{job.state === "FAILED" ? "Source needs attention" : job.state === "READY" ? "Evidence index is ready" : "Preparing grounded evidence…"}</h3></div>
              {progress && progress.total > 0 ? <strong>{progress.completed}/{progress.total} batches</strong> : null}
            </div>
            <ol className="ingestion-stages">
              {STAGES.map((stage, index) => {
                const complete = job.state === "READY" || (currentIndex >= 0 && index < currentIndex);
                const current = index === currentIndex;
                return <li key={stage.state} className={complete ? "is-complete" : current ? "is-current" : ""}><span aria-hidden="true" /> <div><strong>{stage.label}</strong><small>{stage.note}</small></div></li>;
              })}
            </ol>
            {job.state === "FAILED" ? (
              <div className="ingestion-error" role="alert">
                <p><strong>{job.error_code?.replaceAll("_", " ")}</strong>{job.safe_error}</p>
                {failedReplacement ? <p>Your previous Ready source remains active and queryable.</p> : null}
                {editable ? <div>{job.retryable ? <button type="button" className="studio-primary" disabled={busy} onClick={() => void retry()}>{busy ? "Retrying…" : "Retry"}</button> : null}<button type="button" className="quiet-button" disabled={busy} onClick={() => void remove()}>Remove failed source</button></div> : null}
              </div>
            ) : null}
          </div>
        ) : null}

        {notice ? <p className="studio-alert knowledge-alert" role="status">{notice}</p> : null}
        {activeDocument && editable && !processing && job?.state !== "FAILED" ? (
          <button type="button" className="quiet-button remove-source" disabled={busy} onClick={() => void remove()}>Remove source</button>
        ) : null}
      </div>
    </section>
  );
}
