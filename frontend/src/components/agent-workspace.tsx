"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { KnowledgePanel } from "@/components/knowledge-panel";
import { PlaygroundPanel } from "@/components/playground-panel";
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

type WorkspaceStage = "define" | "knowledge" | "test" | "submit";

const WORKSPACE_STAGES: Array<{ id: WorkspaceStage; number: string; label: string }> = [
  { id: "define", number: "01", label: "Define" },
  { id: "knowledge", number: "02", label: "Knowledge" },
  { id: "test", number: "03", label: "Test" },
  { id: "submit", number: "04", label: "Submit" },
];

function stageFromHash(hash: string): WorkspaceStage | null {
  const candidate = hash.replace(/^#/, "");
  return WORKSPACE_STAGES.some((stage) => stage.id === candidate)
    ? candidate as WorkspaceStage
    : null;
}

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
  const [activeStage, setActiveStage] = useState<WorkspaceStage>("define");
  const submitKey = useRef<string | null>(null);
  const knowledgeReady = state.phase === "ready" && state.version.knowledge_status === "READY";

  const replaceVersion = useCallback((version: VersionDetail) => {
    setState((current) => current.phase === "ready" ? { ...current, version } : current);
  }, []);
  const sessionExpired = useCallback(() => {
    router.replace("/access?reason=expired");
  }, [router]);

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

  useEffect(() => {
    if (state.phase !== "ready") return;

    const restoreStage = () => {
      const requested = stageFromHash(window.location.hash);
      const unlocked = requested !== "test" && requested !== "submit" || knowledgeReady;
      const nextStage = requested && unlocked ? requested : requested ? "knowledge" : "define";
      setActiveStage(nextStage);
      if (window.location.hash !== `#${nextStage}`) {
        window.history.replaceState(null, "", `#${nextStage}`);
      }
    };

    restoreStage();
    window.addEventListener("popstate", restoreStage);
    window.addEventListener("hashchange", restoreStage);
    return () => {
      window.removeEventListener("popstate", restoreStage);
      window.removeEventListener("hashchange", restoreStage);
    };
  }, [knowledgeReady, state.phase]);

  function selectStage(stage: WorkspaceStage) {
    if ((stage === "test" || stage === "submit") && !knowledgeReady) return;
    if (stage !== activeStage) window.history.pushState(null, "", `#${stage}`);
    setActiveStage(stage);
    window.requestAnimationFrame(() => {
      document.getElementById(`workspace-panel-${stage}`)?.focus();
    });
  }

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

  async function submitForReview() {
    if (state.phase !== "ready" || pending || !knowledgeReady) return;
    setPending(true);
    setNotice(null);
    submitKey.current ??= crypto.randomUUID();
    try {
      await studioApi.submitVersion(state.version.id, state.csrf, submitKey.current);
      submitKey.current = null;
      router.push(`/studio/review/${agentId}`);
    } catch (error) {
      if (!(error instanceof ApiError && error.retryable)) submitKey.current = null;
      if (error instanceof ApiError && error.status === 401) sessionExpired();
      else setNotice(error instanceof Error ? error.message : "The version could not be submitted.");
      setPending(false);
    }
  }

  if (state.phase === "loading") return <main className="studio-loading" aria-live="polite"><span className="ocean-loader" aria-hidden="true" /><p>Opening Agent Draft…</p></main>;
  if (state.phase === "error") return <main className="studio-loading" aria-live="assertive"><p className="eyebrow">{state.missing ? "Draft not found" : "Workspace interrupted"}</p><h1>{state.message}</h1><div className="error-actions"><Link href="/studio">Back to workshop</Link>{!state.missing ? <button className="studio-primary" onClick={() => { setState({ phase: "loading" }); void load(); }}>Try again</button> : null}</div></main>;

  const editable = state.role === "STUDENT" && state.version.allowed_actions.includes("EDIT_DRAFT");
  const knowledgeProcessing = state.version.knowledge_status === "PROCESSING";
  const stageStatus: Record<WorkspaceStage, string> = {
    define: "Drafted",
    knowledge: knowledgeReady ? "Ready" : knowledgeProcessing ? "Processing" : "In progress",
    test: knowledgeReady ? "Open" : "Locked",
    submit: knowledgeReady ? "Ready" : "Locked",
  };
  return (
    <StudioShell role={state.role} busy={pending} onRoleChange={(role) => void changeRole(role)} onSignOut={() => void signOut()}>
      <main className="workspace-main">
        <div className="workspace-breadcrumb"><Link href="/studio">Workshop</Link><span>/</span><strong>Agent workspace</strong></div>
        <section className="workspace-heading">
          <div><p className="eyebrow">Agent workspace</p><h1>{state.version.project_name}</h1><p>Move through each stage, test real behavior, then submit an immutable version.</p></div>
          <dl className="workspace-context"><div><dt>Version</dt><dd>v{state.version.version_number}</dd></div><div><dt>State</dt><dd>{state.version.state.replaceAll("_", " ")}</dd></div><div><dt>Knowledge</dt><dd>{state.version.knowledge_status.replaceAll("_", " ")}</dd></div></dl>
        </section>
        {state.version.version_number > 1 ? <section className="reflection-banner"><p className="eyebrow">Iteration reflection</p><div><p><strong>What changed</strong>{state.version.what_changed}</p><p><strong>Why changed</strong>{state.version.why_changed}</p></div></section> : null}
        <nav className="workspace-stage-nav" aria-label="Agent build stages">
          <ol className="workspace-steps">
            {WORKSPACE_STAGES.map((stage) => {
              const locked = (stage.id === "test" || stage.id === "submit") && !knowledgeReady;
              const complete = stage.id === "define" || stage.id === "knowledge" && knowledgeReady;
              return (
                <li key={stage.id} className={`${activeStage === stage.id ? "is-current" : ""} ${complete ? "is-complete" : ""} ${locked ? "is-locked" : "is-available"}`}>
                  <button
                    type="button"
                    aria-current={activeStage === stage.id ? "step" : undefined}
                    aria-controls={`workspace-panel-${stage.id}`}
                    disabled={locked}
                    onClick={() => selectStage(stage.id)}
                  >
                    <span>{stage.number}</span><strong>{stage.label}</strong><small>{stageStatus[stage.id]}</small>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        <div id="workspace-panel-define" className="workspace-stage-panel" tabIndex={-1} hidden={activeStage !== "define"}>
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
        </div>

        <div id="workspace-panel-knowledge" className="workspace-stage-panel" tabIndex={-1} hidden={activeStage !== "knowledge"}>
          <KnowledgePanel
            role={state.role}
            csrf={state.csrf}
            version={state.version}
            onVersionChange={replaceVersion}
            onSessionExpired={sessionExpired}
          />
        </div>

        <div id="workspace-panel-test" className="workspace-stage-panel" tabIndex={-1} hidden={activeStage !== "test"}>
          {knowledgeReady ? (
            <PlaygroundPanel
              role={state.role}
              csrf={state.csrf}
              version={state.version}
              onSessionExpired={sessionExpired}
            />
          ) : <section className="locked-stages" aria-label="Test stage"><LockedStage number="03" title="Test behavior" copy="Add a Ready source before asking grounded questions or trying safety boundaries." /></section>}
        </div>

        <div id="workspace-panel-submit" className="workspace-stage-panel" tabIndex={-1} hidden={activeStage !== "submit"}>
          {knowledgeReady ? (
            <section className="submit-stage" aria-labelledby="submit-title">
              <div><p className="eyebrow">04 · Submit</p><h2 id="submit-title">Lock v{state.version.version_number} for Teacher review.</h2><p>Submission freezes this configuration and knowledge source. The Teacher can then run the fixed 16-case suite.</p></div>
              {state.role === "STUDENT" ? <button className="studio-primary" type="button" disabled={pending} onClick={() => void submitForReview()}>{pending ? "Submitting once…" : `Submit v${state.version.version_number} for review`}</button> : <p className="read-only-note">Switch to Student to submit this Draft.</p>}
              {notice ? <p className="studio-alert" role="status">{notice}</p> : null}
            </section>
          ) : <section className="locked-stages" aria-label="Submit stage"><LockedStage number="04" title="Request review" copy="Submit only after knowledge and safety checks are complete." /></section>}
        </div>
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
