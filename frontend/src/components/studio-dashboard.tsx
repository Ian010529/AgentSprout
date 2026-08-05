"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { StudioShell } from "@/components/studio-shell";
import {
  ApiError,
  type AgentCreate,
  type AgentSummary,
  type Role,
  studioApi,
} from "@/lib/api";

type DashboardState =
  | { phase: "loading" }
  | { phase: "ready"; role: Role; csrf: string; expiresAt: string; agents: AgentSummary[] }
  | { phase: "error"; message: string; retryable: boolean };

const initialAgent: AgentCreate = {
  template: "KNOWLEDGE_EXPLORER",
  project_name: "Ocean Explorer",
  problem_to_solve: "Help learners understand the ocean using trusted evidence.",
  intended_users: "Students learning ocean science",
  audience_age: "AGE_12_17",
  success_goal: "Answer ocean questions clearly with evidence from the source.",
  welcome_message: "What would you like to discover about the ocean?",
  tone: "CURIOUS",
  response_length: "BALANCED",
  custom_instructions: "",
};

function messageFor(error: unknown): string {
  if (!(error instanceof ApiError)) return "The Studio could not load.";
  if (error.status === 429) return "The Studio is busy. Wait a moment, then try again.";
  if (error.code === "TIMEOUT") return "The Studio took too long to respond.";
  return error.message;
}

export function StudioDashboard() {
  const router = useRouter();
  const [state, setState] = useState<DashboardState>({ phase: "loading" });
  const [showCreate, setShowCreate] = useState(false);
  const [draft, setDraft] = useState<AgentCreate>(initialAgent);
  const [mutationPending, setMutationPending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const idempotencyKey = useRef<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const sessionPromise = studioApi.restore(signal);
      const agentsPromise = studioApi.listAgents(signal);
      const [session, agents] = await Promise.all([sessionPromise, agentsPromise]);
      setState({
        phase: "ready",
        role: session.session.role,
        csrf: session.csrf_token,
        expiresAt: session.session.expires_at,
        agents: agents.agents,
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        router.replace("/access?reason=expired");
        return;
      }
      if (!(error instanceof ApiError && error.code === "CANCELLED")) {
        setState({
          phase: "error",
          message: messageFor(error),
          retryable: error instanceof ApiError ? error.retryable : true,
        });
      }
    }
  }, [router]);

  useEffect(() => {
    const controller = new AbortController();
    const task = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(task);
      controller.abort();
    };
  }, [load]);

  async function changeRole(role: Role) {
    if (state.phase !== "ready" || state.role === role || mutationPending) return;
    setMutationPending(true);
    setFormError(null);
    try {
      const session = await studioApi.changeRole(role, state.csrf);
      const agents = await studioApi.listAgents();
      setShowCreate(false);
      setState({
        phase: "ready",
        role: session.session.role,
        csrf: session.csrf_token,
        expiresAt: session.session.expires_at,
        agents: agents.agents,
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) router.replace("/access?reason=expired");
      else setFormError(messageFor(error));
    } finally {
      setMutationPending(false);
    }
  }

  async function signOut() {
    if (state.phase !== "ready" || mutationPending) return;
    setMutationPending(true);
    try {
      await studioApi.signOut(state.csrf);
      router.replace("/access");
    } catch (error) {
      setFormError(messageFor(error));
      setMutationPending(false);
    }
  }

  function updateDraft<K extends keyof AgentCreate>(field: K, value: AgentCreate[K]) {
    idempotencyKey.current = null;
    setDraft((current) => ({ ...current, [field]: value }));
  }

  async function createAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.phase !== "ready" || mutationPending) return;
    setMutationPending(true);
    setFormError(null);
    idempotencyKey.current ??= crypto.randomUUID();
    try {
      const result = await studioApi.createAgent(draft, state.csrf, idempotencyKey.current);
      idempotencyKey.current = null;
      router.push(`/studio/agents/${result.agent.id}`);
    } catch (error) {
      if (!(error instanceof ApiError && error.retryable)) idempotencyKey.current = null;
      if (error instanceof ApiError && error.status === 401) router.replace("/access?reason=expired");
      else setFormError(messageFor(error));
    } finally {
      setMutationPending(false);
    }
  }

  if (state.phase === "loading") {
    return (
      <main className="studio-loading" aria-live="polite" aria-busy="true">
        <span className="ocean-loader" aria-hidden="true" />
        <p>Restoring the workshop…</p>
      </main>
    );
  }
  if (state.phase === "error") {
    return (
      <main className="studio-loading" role="alert">
        <p className="eyebrow">Connection interrupted</p>
        <h1>The workshop did not open.</h1>
        <p>{state.message}</p>
        {state.retryable ? (
          <button className="studio-primary" type="button" onClick={() => { setState({ phase: "loading" }); void load(); }}>
            Try again
          </button>
        ) : null}
      </main>
    );
  }

  const isStudent = state.role === "STUDENT";
  return (
    <StudioShell
      role={state.role}
      busy={mutationPending}
      onRoleChange={(role) => void changeRole(role)}
      onSignOut={() => void signOut()}
    >
      <main className="studio-main">
        <section className="dashboard-heading">
          <div>
            <p className="eyebrow">{isStudent ? "Student workshop" : "Teacher review desk"}</p>
            <h1>{isStudent ? "Build one useful thing." : "Review what is ready."}</h1>
            <p>
              {isStudent
                ? "Start with a learner need, then make every design choice testable."
                : "Submitted agents will appear first, with evidence and release readiness."}
            </p>
          </div>
          <div className="session-note">
            <span>Session</span>
            <strong>Ends {new Date(state.expiresAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</strong>
          </div>
        </section>

        {formError ? <p className="studio-alert" role="alert">{formError}</p> : null}

        {isStudent ? (
          <section className="template-section" aria-labelledby="template-title">
            <div className="section-label">
              <span>01</span>
              <div><p className="eyebrow">Choose a starting point</p><h2 id="template-title">Agent templates</h2></div>
            </div>
            <article className="template-card">
              <div className="template-emblem" aria-hidden="true"><span>OE</span></div>
              <div>
                <p className="card-kicker">Available now</p>
                <h3>Knowledge Explorer</h3>
                <p>Build an age-aware agent that answers from one trusted source and shows its evidence.</p>
                <ul><li>Grounded answers</li><li>Safety boundaries</li><li>Teacher evaluation</li></ul>
              </div>
              <button className="studio-primary" type="button" onClick={() => setShowCreate(true)}>
                Create agent
              </button>
            </article>
          </section>
        ) : (
          <section className="review-shell" aria-labelledby="review-title">
            <p className="eyebrow">Review priority</p>
            <h2 id="review-title">Nothing is waiting for review.</h2>
            <p>Drafts remain visible below, but only submitted versions can be evaluated.</p>
          </section>
        )}

        {showCreate && isStudent ? (
          <CreateAgentForm
            draft={draft}
            pending={mutationPending}
            error={formError}
            onChange={updateDraft}
            onCancel={() => { setShowCreate(false); setFormError(null); }}
            onSubmit={createAgent}
          />
        ) : null}

        <section className="agents-section" aria-labelledby="agents-title">
          <div className="section-label">
            <span>{isStudent ? "02" : "01"}</span>
            <div><p className="eyebrow">Persisted work</p><h2 id="agents-title">{isStudent ? "Your agents" : "All agents"}</h2></div>
          </div>
          {state.agents.length === 0 ? (
            <div className="empty-workbench">
              <span aria-hidden="true">○</span>
              <h3>{isStudent ? "The workbench is clear." : "No agents have been created yet."}</h3>
              <p>{isStudent ? "Create Ocean Explorer from the template above to begin." : "Switch to Student mode to create the first Draft."}</p>
            </div>
          ) : (
            <div className="agent-grid">
              {state.agents.map((agent) => (
                <article className="agent-card" key={agent.id}>
                  <div className="agent-card-top"><span>v{agent.current_version.number}</span><strong>{agent.current_version.state}</strong></div>
                  <h3>{agent.display_name}</h3>
                  <p>{agent.next_action}</p>
                  <div className="knowledge-line"><span aria-hidden="true" /> Knowledge not added</div>
                  <Link href={`/studio/agents/${agent.id}`}>{isStudent ? "Continue Draft →" : "View Draft →"}</Link>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </StudioShell>
  );
}

type CreateAgentFormProps = {
  draft: AgentCreate;
  pending: boolean;
  error: string | null;
  onChange: <K extends keyof AgentCreate>(field: K, value: AgentCreate[K]) => void;
  onCancel: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

function CreateAgentForm({ draft, pending, error, onChange, onCancel, onSubmit }: CreateAgentFormProps) {
  return (
    <section className="creation-sheet" aria-labelledby="create-title">
      <div className="creation-heading"><div><p className="eyebrow">New expedition</p><h2 id="create-title">Define Ocean Explorer</h2></div><button type="button" onClick={onCancel} disabled={pending}>Close</button></div>
      <form className="agent-form" onSubmit={onSubmit}>
        <Field label="Project name" value={draft.project_name} minLength={3} maxLength={80} onChange={(value) => onChange("project_name", value)} />
        <Field label="Problem to solve" value={draft.problem_to_solve} minLength={10} maxLength={500} textarea onChange={(value) => onChange("problem_to_solve", value)} />
        <Field label="Intended users" value={draft.intended_users} minLength={3} maxLength={240} onChange={(value) => onChange("intended_users", value)} />
        <label>Audience age<select value={draft.audience_age} onChange={(event) => onChange("audience_age", event.target.value as AgentCreate["audience_age"])}><option value="AGE_7_11">Ages 7–11</option><option value="AGE_12_17">Ages 12–17</option></select></label>
        <Field label="Success goal" value={draft.success_goal} minLength={10} maxLength={300} textarea onChange={(value) => onChange("success_goal", value)} />
        <Field label="Welcome message" value={draft.welcome_message} minLength={3} maxLength={240} onChange={(value) => onChange("welcome_message", value)} />
        <label>Tone<select value={draft.tone} onChange={(event) => onChange("tone", event.target.value as AgentCreate["tone"])}><option value="CURIOUS">Curious</option><option value="FRIENDLY">Friendly</option><option value="COACH_LIKE">Coach-like</option></select></label>
        <label>Response length<select value={draft.response_length} onChange={(event) => onChange("response_length", event.target.value as AgentCreate["response_length"])}><option value="BALANCED">Balanced</option><option value="SHORT">Short</option></select></label>
        <Field label="Custom instructions (optional)" value={draft.custom_instructions} maxLength={500} textarea required={false} onChange={(value) => onChange("custom_instructions", value)} />
        {error ? <p className="form-error form-span" role="alert">{error}</p> : null}
        <div className="form-actions form-span"><button type="button" onClick={onCancel} disabled={pending}>Cancel</button><button className="studio-primary" type="submit" disabled={pending}>{pending ? "Creating once…" : "Create Ocean Explorer"}</button></div>
      </form>
    </section>
  );
}

type FieldProps = { label: string; value: string; minLength?: number; maxLength: number; textarea?: boolean; required?: boolean; onChange: (value: string) => void };
function Field({ label, value, minLength, maxLength, textarea, required = true, onChange }: FieldProps) {
  return <label>{label}{textarea ? <textarea value={value} minLength={minLength} maxLength={maxLength} required={required} onChange={(event) => onChange(event.target.value)} /> : <input value={value} minLength={minLength} maxLength={maxLength} required={required} onChange={(event) => onChange(event.target.value)} />}</label>;
}
