"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

import {
  ApiError,
  type ChatResult,
  type PublicAgent,
  publicApi,
} from "@/lib/api";

type PublicMessage = {
  id: string;
  role: "USER" | "ASSISTANT";
  content: string;
  result?: ChatResult;
};

export function PublishedAgent({ slug }: { slug: string }) {
  const [agent, setAgent] = useState<PublicAgent | null>(null);
  const [messages, setMessages] = useState<PublicMessage[]>([]);
  const [message, setMessage] = useState("");
  const [stage, setStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryAfter, setRetryAfter] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const key = useRef<string | null>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    void publicApi
      .getAgent(slug, controller.signal)
      .then((value) => {
        setAgent(value);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (!(cause instanceof ApiError && cause.code === "CANCELLED")) {
          setError(cause instanceof Error ? cause.message : "This Agent could not open.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [slug]);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prompt = message.trim();
    if (!agent || !prompt || sending) return;
    setSending(true);
    setError(null);
    setRetryAfter(null);
    setStage("Checking privacy…");
    key.current ??= crypto.randomUUID();
    const userMessage: PublicMessage = { id: crypto.randomUUID(), role: "USER", content: prompt };
    setMessages((current) => [...current, userMessage]);
    setMessage("");
    try {
      const started = await publicApi.startRun(agent.slug, prompt, key.current);
      key.current = null;
      const deadline = Date.now() + 90_000;
      while (Date.now() < deadline) {
        const run = await publicApi.getRun(started.run_id, started.run_token);
        setStage(run.display_stage);
        if (run.status === "COMPLETED" && run.result) {
          setMessages((current) => [
            ...current,
            {
              id: crypto.randomUUID(),
              role: "ASSISTANT",
              content: run.result!.answer,
              result: run.result!,
            },
          ]);
          setStage(null);
          window.setTimeout(() => resultHeading.current?.focus(), 0);
          return;
        }
        if (run.status === "FAILED") {
          throw new ApiError(
            run.safe_error ?? "The public Agent could not answer safely.",
            null,
            "PUBLIC_RUN_FAILED",
            null,
            run.retryable,
          );
        }
        await new Promise((resolve) => window.setTimeout(resolve, started.poll_after_ms));
      }
      throw new ApiError("The answer timed out. Try again.", null, "TIMEOUT", null, true);
    } catch (cause) {
      const apiError = cause instanceof ApiError ? cause : null;
      if (!apiError?.retryable) key.current = null;
      setMessages((current) => current.filter((item) => item.id !== userMessage.id));
      setMessage(prompt);
      setError(cause instanceof Error ? cause.message : "The public Agent could not answer.");
      setRetryAfter(apiError?.retryAfterSeconds ?? null);
      setStage(null);
    } finally {
      setSending(false);
    }
  }

  if (loading) {
    return (
      <main className="public-status" aria-live="polite">
        <span className="ocean-loader" />
        <p>Opening the published Agent…</p>
      </main>
    );
  }
  if (!agent) {
    return (
      <main className="public-status" role="alert">
        <p className="eyebrow">Published Agent unavailable</p>
        <h1>This learning Agent is not available.</h1>
        <p>{error}</p>
        <Link href="/">Learn about AgentSprout</Link>
      </main>
    );
  }

  return (
    <div className="public-shell">
      <header className="public-nav">
        <Link href="/" className="public-brand" aria-label="AgentSprout home">
          <span>AS</span>
          AgentSprout
        </Link>
        <p>Approved learning Agent</p>
      </header>
      <main className="public-main">
        <header className="public-agent-bar">
          <div><p className="eyebrow">Built by {agent.builder_label}</p><h1 id="agent-title">{agent.project_name}</h1></div>
          <div className="public-badges" aria-label="Publication status">
            <span>✓ Approved</span>
            <span>Published v{agent.version_number}</span>
          </div>
        </header>
        <div className="public-workspace">
          <section className="public-chat" aria-labelledby="chat-title">
          <header>
            <div>
              <p className="eyebrow">Ask from the source</p>
              <h2 id="chat-title" tabIndex={-1} ref={resultHeading}>
                {agent.welcome_message}
              </h2>
            </div>
            <p className="public-privacy">
              Don’t share your email, phone number, or home address. Public chats disappear
              shortly after your answer.
            </p>
          </header>
          <div className="public-thread" aria-live="polite" aria-busy={sending}>
            {messages.length === 0 ? (
              <div className="public-empty">
                <span>01</span>
                <p>Try asking: “How does the ocean influence climate?”</p>
              </div>
            ) : (
              messages.map((item) => (
                <article className={`public-message is-${item.role.toLowerCase()}`} key={item.id}>
                  <p className="message-role">{item.role === "USER" ? "You" : agent.project_name}</p>
                  <p>{item.content}</p>
                  {item.result?.citations.length ? (
                    <div className="public-citations" aria-label="Source citations">
                      {item.result.citations.map((citation) => (
                        <details key={citation.chunk_id}>
                          <summary>
                            {citation.filename} · page {citation.page_number}
                          </summary>
                          <p>{citation.excerpt}</p>
                        </details>
                      ))}
                    </div>
                  ) : null}
                  {item.result ? <span className="result-kind">{item.result.type}</span> : null}
                </article>
              ))
            )}
            {stage ? <p className="public-stage">{stage}</p> : null}
          </div>
          {error ? (
            <div className="public-error" role="alert">
              <strong>{retryAfter ? "Demo limit reached" : "Answer unavailable"}</strong>
              <p>{error}</p>
              {retryAfter ? <small>Try again in about {retryAfter} seconds.</small> : null}
            </div>
          ) : null}
          <form className="public-composer" onSubmit={send}>
            <label htmlFor="public-message">Your question</label>
            <div>
              <textarea
                id="public-message"
                required
                maxLength={1000}
                rows={2}
                value={message}
                disabled={sending}
                onChange={(event) => setMessage(event.target.value)}
              />
              <button disabled={sending || !message.trim()}>
                {sending ? "Working…" : "Ask Agent"}
              </button>
            </div>
          </form>
          </section>
          <aside className="public-about" aria-labelledby="about-agent-title">
            <div><p className="eyebrow">About this Agent</p><h2 id="about-agent-title">What it is here to do</h2><p className="public-lede">{agent.problem_to_solve}</p></div>
            <dl className="public-goals"><div><dt>Designed for</dt><dd>{agent.intended_users}</dd></div><div><dt>Learning goal</dt><dd>{agent.success_goal}</dd></div><div><dt>Audience</dt><dd>{agent.audience_age === "AGE_7_11" ? "Ages 7–11" : "Ages 12–17"}</dd></div></dl>
            <footer className="public-source"><div><p className="eyebrow">Knowledge source</p><strong>{agent.knowledge_source.title}</strong><p>{agent.knowledge_source.author} · {agent.knowledge_source.license}</p></div><a href={agent.knowledge_source.source_url} target="_blank" rel="noreferrer">View source <span aria-hidden="true">↗</span></a><p className="public-disclaimer">Supervised concept demo—not approved for unsupervised child use or emergency help.</p></footer>
          </aside>
        </div>
      </main>
    </div>
  );
}
