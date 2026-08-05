"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { StudioShell } from "@/components/studio-shell";
import {
  ApiError,
  type AgentFields,
  type Role,
  type VersionDetail,
  studioApi,
} from "@/lib/api";

type WorkspaceState =
  | { phase: "loading" }
  | { phase: "error"; message: string; missing: boolean }
  | { phase: "ready"; role: Role; csrf: string; version: VersionDetail };

function editableFields(version: VersionDetail): AgentFields {
  return {
    project_name: version.project_name,
    problem_to_solve: version.problem_to_solve,
    intended_users: version.intended_users,
    audience_age: version.audience_age,
    success_goal: version.success_goal,
    welcome_message: version.welcome_message,
    tone: version.tone,
    response_length: version.response_length,
    custom_instructions: version.custom_instructions,
  };
}

export function AgentWorkspace({ agentId }: { agentId: string }) {
  const router = useRouter();
  const [state, setState] = useState<WorkspaceState>({ phase: "loading" });
  const [draft, setDraft] = useState<AgentFields | null>(null);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const sessionPromise = studioApi.restore(signal);
      const agentPromise = studioApi.getAgent(agentId, signal);
      const [session, agent] = await Promise.all([sessionPromise, agentPromise]);
      if (!agent.current_draft_version_id) throw new Error("This Agent has no editable Draft.");
      const version = await studioApi.getVersion(agent.current_draft_version_id, signal);
      setDraft(editableFields(version));
      setState({ phase: "ready", role: session.session.role, csrf: session.csrf_token, version });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return router.replace("/access?reason=expired");
      if (!(error instanceof ApiError && error.code === "CANCELLED")) {
        setState({
          phase: "error",
          message: error instanceof Error ? error.message : "The Agent workspace could not open.",
          missing: error instanceof ApiError && error.status === 404,
        });
      }
    }
  }, [agentId, router]);

  useEffect(() => {
    const controller = new AbortController();
    const task = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(task);
      controller.abort();
    };
  }, [load]);

  async function changeRole(role: Role) {
    if (state.phase !== "ready" || pending || state.role === role) return;
    setPending(true);
    setNotice(null);
    try {
      const session = await studioApi.changeRole(role, state.csrf);
      const version = await studioApi.getVersion(state.version.id);
      setState({ phase: "ready", role: session.session.role, csrf: session.csrf_token, version });
      setDraft(editableFields(version));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "The role could not change.");
    } finally {
      setPending(false);
    }
  }

  async function signOut() {
    if (state.phase !== "ready" || pending) return;
    setPending(true);
    try {
      await studioApi.signOut(state.csrf);
      router.replace("/access");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Sign out failed.");
      setPending(false);
    }
  }

  function update<K extends keyof AgentFields>(field: K, value: AgentFields[K]) {
    setDraft((current) => current ? { ...current, [field]: value } : current);
    setNotice(null);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.phase !== "ready" || !draft || pending) return;
    setPending(true);
    setNotice(null);
    try {
      const version = await studioApi.updateVersion(state.version.id, draft, state.csrf);
      setState({ ...state, version });
      setDraft(editableFields(version));
      setNotice("Draft saved. Refreshing this page will restore these choices.");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) router.replace("/access?reason=expired");
      else setNotice(error instanceof Error ? error.message : "The Draft could not be saved.");
    } finally {
      setPending(false);
    }
  }

  if (state.phase === "loading") return <main className="studio-loading" aria-live="polite"><span className="ocean-loader" aria-hidden="true" /><p>Opening Agent Draft…</p></main>;
  if (state.phase === "error") return <main className="studio-loading" role="alert"><p className="eyebrow">{state.missing ? "Draft not found" : "Workspace interrupted"}</p><h1>{state.message}</h1><div className="error-actions"><Link href="/studio">Back to workshop</Link>{!state.missing ? <button className="studio-primary" onClick={() => { setState({ phase: "loading" }); void load(); }}>Try again</button> : null}</div></main>;

  const editable = state.role === "STUDENT" && state.version.allowed_actions.includes("EDIT_DRAFT");
  return (
    <StudioShell role={state.role} busy={pending} onRoleChange={(role) => void changeRole(role)} onSignOut={() => void signOut()}>
      <main className="workspace-main">
        <div className="workspace-breadcrumb"><Link href="/studio">Workshop</Link><span>/</span><strong>{state.version.project_name}</strong></div>
        <section className="workspace-heading">
          <div><p className="eyebrow">Knowledge Explorer · Version {state.version.version_number}</p><h1>{state.version.project_name}</h1><p>Define the learner need first. Each later stage unlocks only when its real requirement is met.</p></div>
          <span className="draft-stamp">Draft</span>
        </section>
        <ol className="workspace-steps" aria-label="Agent build stages">
          <li className="is-active"><span>01</span><strong>Define</strong><small>In progress</small></li>
          <li><span>02</span><strong>Knowledge</strong><small>Next module</small></li>
          <li><span>03</span><strong>Test</strong><small>Locked</small></li>
          <li><span>04</span><strong>Submit</strong><small>Locked</small></li>
        </ol>

        <section className="define-sheet" aria-labelledby="define-title">
          <div className="define-intro"><p className="eyebrow">01 · Define</p><h2 id="define-title">What should this Agent do?</h2><p>Write for another person on the team: specific enough to test, brief enough to understand.</p>{!editable ? <p className="read-only-note">Teacher view is read-only. Switch to Student to edit this Draft.</p> : null}</div>
          {draft ? (
            <form className="agent-form workspace-form" onSubmit={save}>
              <WorkspaceField label="Project name" value={draft.project_name} minLength={3} maxLength={80} disabled={!editable || pending} onChange={(value) => update("project_name", value)} />
              <WorkspaceField label="Problem to solve" value={draft.problem_to_solve} minLength={10} maxLength={500} textarea disabled={!editable || pending} onChange={(value) => update("problem_to_solve", value)} />
              <WorkspaceField label="Intended users" value={draft.intended_users} minLength={3} maxLength={240} disabled={!editable || pending} onChange={(value) => update("intended_users", value)} />
              <label>Audience age<select value={draft.audience_age} disabled={!editable || pending} onChange={(event) => update("audience_age", event.target.value as AgentFields["audience_age"])}><option value="AGE_7_11">Ages 7–11</option><option value="AGE_12_17">Ages 12–17</option></select></label>
              <WorkspaceField label="Success goal" value={draft.success_goal} minLength={10} maxLength={300} textarea disabled={!editable || pending} onChange={(value) => update("success_goal", value)} />
              <WorkspaceField label="Welcome message" value={draft.welcome_message} minLength={3} maxLength={240} disabled={!editable || pending} onChange={(value) => update("welcome_message", value)} />
              <label>Tone<select value={draft.tone} disabled={!editable || pending} onChange={(event) => update("tone", event.target.value as AgentFields["tone"])}><option value="CURIOUS">Curious</option><option value="FRIENDLY">Friendly</option><option value="COACH_LIKE">Coach-like</option></select></label>
              <label>Response length<select value={draft.response_length} disabled={!editable || pending} onChange={(event) => update("response_length", event.target.value as AgentFields["response_length"])}><option value="BALANCED">Balanced</option><option value="SHORT">Short</option></select></label>
              <WorkspaceField label="Custom instructions (optional)" value={draft.custom_instructions} maxLength={500} textarea required={false} disabled={!editable || pending} onChange={(value) => update("custom_instructions", value)} />
              {notice ? <p className="studio-alert form-span" role="status">{notice}</p> : null}
              {editable ? <div className="form-actions form-span"><span>Saved values remain after refresh.</span><button className="studio-primary" type="submit" disabled={pending}>{pending ? "Saving…" : "Save Draft"}</button></div> : null}
            </form>
          ) : null}
        </section>

        <section className="locked-stages" aria-label="Later build stages">
          <LockedStage number="02" title="Add knowledge" copy="Upload one trusted source and watch its real ingestion stages." />
          <LockedStage number="03" title="Test behavior" copy="Ask grounded questions and try privacy and homework boundaries." />
          <LockedStage number="04" title="Request review" copy="Submit only after knowledge and safety checks are complete." />
        </section>
      </main>
    </StudioShell>
  );
}

type WorkspaceFieldProps = { label: string; value: string; minLength?: number; maxLength: number; textarea?: boolean; required?: boolean; disabled: boolean; onChange: (value: string) => void };
function WorkspaceField({ label, value, minLength, maxLength, textarea, required = true, disabled, onChange }: WorkspaceFieldProps) {
  return <label>{label}{textarea ? <textarea value={value} minLength={minLength} maxLength={maxLength} required={required} disabled={disabled} onChange={(event) => onChange(event.target.value)} /> : <input value={value} minLength={minLength} maxLength={maxLength} required={required} disabled={disabled} onChange={(event) => onChange(event.target.value)} />}</label>;
}

function LockedStage({ number, title, copy }: { number: string; title: string; copy: string }) {
  return <article><span>{number}</span><div><p className="eyebrow">Locked for now</p><h2>{title}</h2><p>{copy}</p></div><strong aria-label="Locked">⌁</strong></article>;
}
