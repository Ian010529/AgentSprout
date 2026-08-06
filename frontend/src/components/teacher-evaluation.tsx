"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { StudioShell } from "@/components/studio-shell";
import {
  ApiError,
  type EvaluationCase,
  type EvaluationCaseDetail,
  type EvaluationCategory,
  type EvaluationRun,
  type Role,
  type VersionDetail,
  type VersionComparison,
  studioApi,
} from "@/lib/api";

type ReadyState = {
  role: Role;
  csrf: string;
  version: VersionDetail;
  runs: EvaluationRun[];
  selected: EvaluationRun | null;
  cases: EvaluationCase[];
  versions: VersionDetail[];
  histories: Record<string, EvaluationRun[]>;
  publishedVersionId: string | null;
};

const categories: Array<{ value: EvaluationCategory | "ALL"; label: string }> = [
  { value: "ALL", label: "All 16" },
  { value: "KNOWLEDGE", label: "Knowledge" },
  { value: "OUT_OF_KNOWLEDGE", label: "Boundary" },
  { value: "PRIVACY", label: "Privacy" },
  { value: "HOMEWORK", label: "Homework" },
  { value: "INJECTION", label: "Injection" },
  { value: "AGE", label: "Age" },
];

export function TeacherEvaluation({ agentId }: { agentId: string }) {
  const router = useRouter();
  const [state, setState] = useState<ReadyState | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<EvaluationCategory | "ALL">("ALL");
  const [detail, setDetail] = useState<EvaluationCaseDetail | null>(null);
  const [feedback, setFeedback] = useState("");
  const [whatChanged, setWhatChanged] = useState("");
  const [whyChanged, setWhyChanged] = useState("");
  const [comparison, setComparison] = useState<VersionComparison | null>(null);
  const [slug, setSlug] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [publicPath, setPublicPath] = useState<string | null>(null);
  const startKey = useRef<string | null>(null);
  const nextKey = useRef<string | null>(null);
  const publishKey = useRef<string | null>(null);
  const withdrawKey = useRef<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const [session, agent] = await Promise.all([studioApi.restore(signal), studioApi.getAgent(agentId, signal)]);
      const versionDetails = await Promise.all(agent.versions.map((item) => studioApi.getVersion(item.id, signal)));
      const latest = versionDetails.at(-1);
      if (!latest) throw new Error("This Agent has no submitted version.");
      const histories: Record<string, EvaluationRun[]> = {};
      if (session.session.role === "TEACHER") {
        await Promise.all(versionDetails.map(async (version) => { histories[version.id] = (await studioApi.listEvaluations(version.id, signal)).evaluations; }));
      }
      const runs = histories[latest.id] ?? [];
      const selected = runs[0] ?? null;
      const cases = selected ? (await studioApi.getEvaluationCases(selected.id, undefined, signal)).cases : [];
      setState({ role: session.session.role, csrf: session.csrf_token, version: latest, versions: versionDetails, histories, runs, selected, cases, publishedVersionId: agent.published_version_id });
      setSlug((current) => current || latest.project_name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""));
      if (agent.published_version_id === latest.id) setPublicPath(`/p/${agent.slug}`);
      setError(null);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) return router.replace("/access?reason=expired");
      if (!(cause instanceof ApiError && cause.code === "CANCELLED")) setError(cause instanceof Error ? cause.message : "The review could not open.");
    } finally {
      setLoading(false);
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
    if (!state?.selected || !["QUEUED", "RUNNING"].includes(state.selected.state)) return;
    const timer = window.setInterval(async () => {
      try {
        const selected = await studioApi.getEvaluation(state.selected!.id);
        const cases = (await studioApi.getEvaluationCases(selected.id)).cases;
        setState((current) => current ? {
          ...current,
          selected,
          cases,
          runs: current.runs.map((run) => run.id === selected.id ? selected : run),
          histories: {
            ...current.histories,
            [current.version.id]: (current.histories[current.version.id] ?? []).map((run) => run.id === selected.id ? selected : run),
          },
        } : current);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Evaluation progress could not refresh.");
      }
    }, 500);
    return () => window.clearInterval(timer);
  }, [state?.selected]);

  async function changeRole(role: Role) {
    if (!state || pending || state.role === role) return;
    setPending(true);
    try {
      await studioApi.changeRole(role, state.csrf);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The role could not change.");
    } finally {
      setPending(false);
    }
  }

  async function signOut() {
    if (!state) return;
    await studioApi.signOut(state.csrf);
    router.replace("/access");
  }

  async function startEvaluation() {
    if (!state || pending || state.role !== "TEACHER") return;
    setPending(true);
    setError(null);
    startKey.current ??= crypto.randomUUID();
    try {
      const started = await studioApi.startEvaluation(state.version.id, state.csrf, startKey.current);
      startKey.current = null;
      const selected = await studioApi.getEvaluation(started.evaluation_run_id);
      setState({
        ...state,
        selected,
        runs: [selected, ...state.runs],
        histories: { ...state.histories, [state.version.id]: [selected, ...(state.histories[state.version.id] ?? [])] },
        cases: [],
      });
    } catch (cause) {
      if (!(cause instanceof ApiError && cause.retryable)) startKey.current = null;
      setError(cause instanceof Error ? cause.message : "The evaluation could not start.");
    } finally {
      setPending(false);
    }
  }

  async function selectRun(run: EvaluationRun) {
    if (!state) return;
    const cases = (await studioApi.getEvaluationCases(run.id)).cases;
    setState({ ...state, selected: run, cases });
    setDetail(null);
  }

  async function inspect(resultId: string) {
    try {
      setDetail(await studioApi.getEvaluationCase(resultId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Case evidence could not open.");
    }
  }

  async function requestChanges(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state?.selected || state.selected.state !== "COMPLETED" || pending) return;
    setPending(true); setError(null);
    try {
      await studioApi.requestChanges(state.version.id, state.selected.id, feedback, state.csrf);
      setFeedback("");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Changes could not be requested."); }
    finally { setPending(false); }
  }

  async function createNext(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state || pending) return;
    setPending(true); setError(null); nextKey.current ??= crypto.randomUUID();
    try {
      await studioApi.createNextVersion(state.version.id, whatChanged, whyChanged, state.csrf, nextKey.current);
      nextKey.current = null;
      router.push(`/studio/agents/${agentId}`);
    } catch (cause) {
      if (!(cause instanceof ApiError && cause.retryable)) nextKey.current = null;
      setError(cause instanceof Error ? cause.message : "The next version could not be created.");
      setPending(false);
    }
  }

  async function approve() {
    if (!state?.selected || pending) return;
    setPending(true); setError(null);
    try { await studioApi.approveVersion(state.version.id, state.selected.id, state.csrf); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "The version could not be approved."); }
    finally { setPending(false); }
  }

  async function publish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state || pending || !confirmed) return;
    setPending(true); setError(null); publishKey.current ??= crypto.randomUUID();
    try {
      const result = await studioApi.publishVersion(state.version.id, slug, state.csrf, publishKey.current);
      publishKey.current = null; setConfirmed(false); setPublicPath(result.public_path); await load();
    } catch (cause) {
      if (!(cause instanceof ApiError && cause.retryable)) publishKey.current = null;
      setError(cause instanceof Error ? cause.message : "The version could not publish.");
    } finally { setPending(false); }
  }

  async function withdraw() {
    if (!state || pending || !confirmed) return;
    setPending(true); setError(null); withdrawKey.current ??= crypto.randomUUID();
    try {
      await studioApi.withdrawVersion(state.version.id, state.csrf, withdrawKey.current);
      withdrawKey.current = null; setConfirmed(false); setPublicPath(null); await load();
    } catch (cause) {
      if (!(cause instanceof ApiError && cause.retryable)) withdrawKey.current = null;
      setError(cause instanceof Error ? cause.message : "The public Agent could not withdraw.");
    } finally { setPending(false); }
  }

  async function compareLatest() {
    if (!state || state.versions.length < 2 || pending) return;
    const leftVersion = state.versions.at(-2)!;
    const rightVersion = state.versions.at(-1)!;
    const leftRun = state.histories[leftVersion.id]?.find((item) => item.state === "COMPLETED");
    const rightRun = state.histories[rightVersion.id]?.find((item) => item.state === "COMPLETED");
    if (!leftRun || !rightRun) return setError("Both versions need completed evaluations before comparison.");
    setPending(true); setError(null);
    try { setComparison(await studioApi.compareVersions(leftVersion.id, rightVersion.id, leftRun.id, rightRun.id)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Versions could not be compared."); }
    finally { setPending(false); }
  }

  if (loading) return <main className="studio-loading" aria-live="polite"><span className="ocean-loader" /><p>Opening Teacher evidence…</p></main>;
  if (!state) return <main className="studio-loading" aria-live="assertive"><h1>Review unavailable.</h1><p>{error}</p><Link href="/studio">Back to workshop</Link></main>;
  const run = state.selected;
  const visible = filter === "ALL" ? state.cases : state.cases.filter((item) => item.category === filter);
  const active = run && ["QUEUED", "RUNNING"].includes(run.state);
  return (
    <StudioShell role={state.role} activeSection="reviews" busy={pending} onRoleChange={(role) => void changeRole(role)} onSignOut={() => void signOut()}>
      <main className="evaluation-main">
        <div className="workspace-breadcrumb"><Link href="/studio">Workshop</Link><span>/</span><strong>Teacher evidence</strong></div>
        <section className="evaluation-hero">
          <div><p className="eyebrow">Ocean Explorer · immutable v{state.version.version_number}</p><h1>Prove the Agent<br />before release.</h1><p>Sixteen fixed cases replay the real runtime. Scores are computed from persisted evidence—not editable fields.</p></div>
          <div className="evaluation-action"><span className="review-stamp">{state.version.state.replace("_", " ")}</span>{state.role === "TEACHER" ? <button className="studio-primary" disabled={pending || Boolean(active)} onClick={() => void startEvaluation()}>{active ? "Evaluation running…" : "Run 16-case evaluation"}</button> : <p>Switch to Teacher to run or inspect evaluations.</p>}</div>
        </section>
        <section className="version-timeline" aria-label="Version timeline">
          {state.versions.map((version) => <article key={version.id} className={version.id === state.version.id ? "is-current" : ""}><span>v{version.version_number}</span><strong>{version.state.replaceAll("_", " ")}</strong><small>{version.knowledge_status}</small></article>)}
        </section>
        {state.version.what_changed ? <section className="review-reflection"><p className="eyebrow">Student reflection</p><div><p><strong>What changed</strong>{state.version.what_changed}</p><p><strong>Why changed</strong>{state.version.why_changed}</p></div></section> : null}
        {(state.version.reviews ?? []).filter((review) => review.feedback).map((review) => <section className="teacher-feedback" key={review.id}><p className="eyebrow">Teacher feedback</p><p>{review.feedback}</p></section>)}
        {error ? <p className="studio-alert" role="alert">{error}</p> : null}
        {state.role === "STUDENT" && state.version.state === "CHANGES_REQUESTED" ? <form className="iteration-form" onSubmit={createNext}><div><p className="eyebrow">Create v{state.version.version_number + 1}</p><h2>Turn feedback into a testable change.</h2><p>The Ready source is copied without another embedding call and remains isolated by version.</p></div><label>What changed<textarea required minLength={3} maxLength={500} value={whatChanged} onChange={(event) => setWhatChanged(event.target.value)} /></label><label>Why changed<textarea required minLength={3} maxLength={500} value={whyChanged} onChange={(event) => setWhyChanged(event.target.value)} /></label><button className="studio-primary" disabled={pending}>{pending ? "Creating once…" : `Create Draft v${state.version.version_number + 1}`}</button></form> : null}
        {state.role !== "TEACHER" ? <section className="evaluation-empty"><p className="eyebrow">Submitted snapshot</p><h2>This version is locked.</h2><p>The configuration and Ready NOAA source cannot be changed while it waits for Teacher evaluation.</p></section> : run ? (
          <>
            <section className="evaluation-progress" aria-live="polite">
              <div><p className="eyebrow">{run.state}</p><strong>{run.progress.completed}<span>/16</span></strong><p>cases persisted</p></div>
              <div className="evaluation-meter"><i style={{ width: `${run.progress.completed / 16 * 100}%` }} /><span>{active ? "Running at most three cases concurrently" : run.release_eligible ? "Release gate passed" : "Release gate blocked"}</span></div>
              <dl><div><dt>Passed</dt><dd>{run.progress.passed}</dd></div><div><dt>Failed</dt><dd>{run.progress.failed}</dd></div><div><dt>Infra errors</dt><dd>{run.progress.errors}</dd></div><div><dt>Cost</dt><dd>${run.usage.estimated_cost_usd.toFixed(4)}</dd></div></dl>
            </section>
            <section className="evaluation-baseline"><label><p>Evaluation run</p><select aria-label="Evaluation run" value={run.id} onChange={(event) => { const selected = state.runs.find((item) => item.id === event.target.value); if (selected) void selectRun(selected); }}>{state.runs.map((item, index) => <option value={item.id} key={item.id}>Run {state.runs.length - index} · {item.state}</option>)}</select></label><div><p>Online</p><strong>{run.models.online}</strong></div><div><p>Judge</p><strong>{run.models.judge}</strong></div><div><p>Tokens</p><strong>{run.usage.input_tokens + run.usage.output_tokens}</strong></div>{run.metrics ? <><div><p>Grounded</p><strong>{Math.round(run.metrics.grounded_pass_rate * 100)}%</strong></div><div><p>Age / instruction</p><strong>{run.metrics.age_average.toFixed(1)} / {run.metrics.instruction_average.toFixed(1)}</strong></div></> : null}</section>
            <section className="evaluation-cases">
              <header><div><p className="eyebrow">Case evidence</p><h2>Every decision has a trail.</h2></div><label>Filter cases<select value={filter} onChange={(event) => setFilter(event.target.value as EvaluationCategory | "ALL")}>{categories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label></header>
              <div className="case-table" role="table" aria-label="Evaluation cases">{visible.map((item) => <button key={item.id} role="row" onClick={() => void inspect(item.id)}><span>{item.case_key}</span><span>{item.category.replaceAll("_", " ")}</span><span>{item.actual_result_type ?? item.state}</span><strong className={item.state === "ERROR" ? "is-error" : item.passed ? "is-pass" : "is-fail"}>{item.state === "ERROR" ? "ERROR" : item.passed ? "PASS" : item.state === "COMPLETED" ? "FAIL" : item.state}</strong></button>)}</div>
            </section>
            {state.role === "TEACHER" && run.state === "COMPLETED" && state.version.state === "IN_REVIEW" ? <section className="review-decisions"><form onSubmit={requestChanges}><p className="eyebrow">Needs another iteration</p><h2>Request specific changes.</h2><label>Required feedback<textarea required minLength={3} maxLength={1000} value={feedback} onChange={(event) => setFeedback(event.target.value)} /></label><button disabled={pending}>Request changes</button></form><div><p className="eyebrow">Release decision</p><h2>{run.release_eligible ? "This run can be approved." : "Release gate is blocked."}</h2><p>{run.release_eligible ? "Approval keeps this version immutable and does not publish it." : "Resolve blocking cases or infrastructure errors, submit a new version, and evaluate again."}</p><button className="studio-primary" disabled={pending || !run.release_eligible} onClick={() => void approve()}>Approve v{state.version.version_number}</button></div></section> : null}
            {state.role === "TEACHER" && state.version.state === "APPROVED" ? <form className="publication-panel" onSubmit={publish}><div><p className="eyebrow">Approved for release</p><h2>Publish a stable public address.</h2><p>The public page exposes only approved metadata and a privacy-minimizing chat. Studio evidence remains private.</p></div><label>Public slug<input required minLength={3} maxLength={60} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={slug} onChange={(event) => setSlug(event.target.value)} /></label><label className="publish-confirm"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> I confirm this Approved version should be public.</label><button className="studio-primary" disabled={pending || !confirmed}>{pending ? "Publishing once…" : `Publish v${state.version.version_number}`}</button></form> : null}
            {state.role === "TEACHER" && state.publishedVersionId === state.version.id ? <section className="publication-panel is-live"><div><p className="eyebrow">Public now</p><h2>Published Agent is live.</h2><p>Withdrawing removes public availability without deleting evaluation or knowledge evidence.</p>{publicPath ? <Link href={publicPath} target="_blank">Open {publicPath} ↗</Link> : null}</div><label className="publish-confirm"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> I confirm this public version should be withdrawn.</label><button disabled={pending || !confirmed} onClick={() => void withdraw()}>{pending ? "Withdrawing once…" : "Withdraw public Agent"}</button></section> : null}
            {state.role === "TEACHER" && state.versions.length > 1 ? <section className="comparison-panel"><header><div><p className="eyebrow">Version evidence</p><h2>Compare like with like.</h2></div><button disabled={pending} onClick={() => void compareLatest()}>Compare latest completed runs</button></header>{comparison ? <><div className="comparison-deltas"><span>Grounded <strong>{comparison.deltas.grounded_pass_rate >= 0 ? "+" : ""}{Math.round(comparison.deltas.grounded_pass_rate * 100)} pts</strong></span><span>Age <strong>{comparison.deltas.age_average.toFixed(2)}</strong></span><span>Tokens <strong>{comparison.deltas.input_tokens + comparison.deltas.output_tokens}</strong></span><span>Latency <strong>{comparison.deltas.latency_ms} ms</strong></span><span>Cost <strong>${comparison.deltas.estimated_cost_usd.toFixed(5)}</strong></span></div><div className="comparison-cases">{comparison.cases.map((item) => <span className={item.transition.toLowerCase()} key={item.case_key}>{item.case_key}<strong>{item.transition}</strong></span>)}</div></> : <p>Selecting comparison verifies suite and model baselines on the server.</p>}</section> : null}
          </>
        ) : <section className="evaluation-empty"><p className="eyebrow">No run yet</p><h2>Start with the fixed suite.</h2><p>The first persisted case will appear here as soon as it completes. Refresh restoration is automatic.</p></section>}
      </main>
      {detail ? <aside className="case-detail" aria-label="Evaluation case evidence"><button aria-label="Close case evidence" onClick={() => setDetail(null)}>×</button><p className="eyebrow">{detail.case_key} · {detail.category.replaceAll("_", " ")}</p><h2>{detail.passed ? "Passed with evidence" : "Needs attention"}</h2><p>{detail.safe_prompt}</p><dl><div><dt>Expected</dt><dd>{detail.expected_result_type}</dd></div><div><dt>Observed</dt><dd>{detail.actual_result_type ?? "—"}</dd></div><div><dt>Latency</dt><dd>{detail.latency_ms} ms</dd></div></dl><h3>Deterministic checks</h3>{Object.entries(detail.deterministic_checks).map(([key, passed]) => <p className="detail-check" key={key}><span>{passed ? "✓" : "×"}</span>{key.replaceAll("_", " ")}</p>)}{detail.judge ? <><h3>Teacher Judge</h3><p>{String(detail.judge.rationale)}</p><div className="judge-scores"><span>Evidence {detail.judge.evidence_score}/5</span><span>Age {detail.judge.age_score}/5</span><span>Instruction {detail.judge.instruction_score}/5</span></div></> : null}</aside> : null}
    </StudioShell>
  );
}
