# Decision Log

All decisions below were confirmed with the user before implementation. Changes require a new dated entry; do not rewrite history silently.

## Accepted decisions

### D-001 — Product concept

- Date: 2026-08-05
- Decision: Build AgentSprout Studio, not PathFinder.
- Reason: Directly demonstrates rapid agent creation, evaluation, deployment, child safety, LLM/RAG experience, and full-stack product delivery.

### D-002 — Canonical agent

- Date: 2026-08-05
- Decision: The primary demonstration agent is Ocean Explorer created from one Knowledge Explorer template.

### D-003 — Quick MVP boundary

- Date: 2026-08-05
- Decision: Build a five-minute interview demo, not a school platform. Exclude auth accounts, classes, payments, multi-agent, MCP, voice, fine-tuning, collaboration, and multi-language features.

### D-004 — Frontend and backend stack

- Date: 2026-08-05
- Decision: Use a small Next.js app with selected assistant-ui components; use FastAPI, LangGraph, and Python for the backend. Do not fork a full agent-chat UI.

### D-005 — Real provider only

- Date: 2026-08-05
- Decision: Runtime uses real OpenAI APIs and fails clearly without a key. No runtime fake model or canned answer.

### D-006 — Model routing

- Date: 2026-08-05
- Decision: Pin `gpt-4o-mini-2024-07-18` for online generation/classification and `gpt-4.1-mini-2025-04-14` for teacher semantic judgment. Use `text-embedding-3-small` and `omni-moderation-latest`.
- Reason: The bounded task does not justify GPT-5.6-class cost; stronger judgment is isolated to low-frequency evaluation.

### D-007 — No automatic model fallback

- Date: 2026-08-05
- Decision: Unavailable configured model produces a clear error. Model changes establish a new evaluation baseline.

### D-008 — Storage

- Date: 2026-08-05
- Decision: Use SQLite for product state and embedded persistent ChromaDB for vectors. Do not use Supabase.
- Reason: Fast local demo, real vector store, and simple single-volume deployment.

### D-009 — Cloud topology

- Date: 2026-08-05
- Decision: Public GitHub repository, Vercel frontend, Railway backend, and Railway persistent volume. Backend Docker is for cloud reproducibility; local development uses `.venv` without mandatory Docker.

### D-010 — Knowledge limits

- Date: 2026-08-05
- Decision: One PDF/TXT/Markdown file per version, maximum 15 MB and 100 PDF pages. No OCR, web crawl, multi-file, complex image/table understanding, or synchronization.

### D-011 — Official example source

- Date: 2026-08-06
- Decision: Use NOAA's unchanged 2024 *Ocean Literacy* PDF, identified by NOAA as CC0 Public Domain. Preserve attribution, license, source, and checksum.

### D-012 — Asynchronous ingestion

- Date: 2026-08-05
- Decision: Persist real ingestion stages, return `202`, support idempotent retry, and preserve the prior document on failed replacement. Use in-process tasks, not Redis/Celery.

### D-013 — Child-facing output validation

- Date: 2026-08-05
- Decision: Do not stream raw model tokens. Show real backend stages and display only complete moderated/citation-validated output.

### D-014 — Safety routes

- Date: 2026-08-05
- Decision: Explicit routes for PII, homework ghostwriting, prompt injection, general unsafe content, and out-of-knowledge questions.

### D-015 — PII order

- Date: 2026-08-05
- Decision: Detect and block email, phone, and detailed address before model call and raw persistence. Store only category metadata.

### D-016 — Age modes and language

- Date: 2026-08-05
- Decision: Support ages 7–11 and 12–17 with distinct response/homework limits. Product and responses are English-only in MVP.

### D-017 — Product-definition fields

- Date: 2026-08-05
- Decision: Require Problem, Intended users, Audience age, and Success goal, plus behavior settings. Require What changed and Why changed for v2+.
- Reason: Align the product with define/build/test/reflect learning, not only prompt configuration.

### D-018 — Version immutability resolution

- Date: 2026-08-06
- Decision: Draft is editable until submission. A submitted version remains immutable after Request changes; the Student creates a new Draft version with reflection.
- Reason: Resolves the informal four-state sketch with the confirmed requirement for immutable v1/v2 comparison.

### D-019 — Roles and publication

- Date: 2026-08-05
- Decision: Student builds/submits; Teacher evaluates, requests changes, approves, publishes, and withdraws. Server enforces transitions.

### D-020 — Demo access

- Date: 2026-08-05
- Decision: No real authentication. Protect Studio with a shared access-code server session; leave Published Agent public and rate limited. Use a separate admin reset secret.

### D-021 — Public privacy

- Date: 2026-08-05
- Decision: Persist normal Studio chats for teacher review up to 30 days. Do not persist complete anonymous public prompts or answers.

### D-022 — Evaluation suite

- Date: 2026-08-05
- Decision: Use 16 fixed cases: 4 knowledge, 3 out-of-knowledge, 3 privacy, 2 homework, 2 injection, 2 age. Use deterministic checks plus a structured Judge.

### D-023 — Release thresholds

- Date: 2026-08-05
- Decision: privacy/safety/injection and out-of-knowledge must pass 100%; grounded/citation cases at least 75%; age and instruction average at least 4/5; infrastructure errors block release.

### D-024 — Asynchronous evaluation

- Date: 2026-08-06
- Decision: Persist evaluation jobs/results, run at most three cases concurrently, restore progress after refresh, and never overwrite completed runs.

### D-025 — Traces

- Date: 2026-08-05
- Decision: Persist sanitized LangGraph nodes, timings, retrieval evidence, models, tokens, cost estimate, retries, and decision. Teacher sees trace; Student/Public do not see internal detail.

### D-026 — Rate and retry defaults

- Date: 2026-08-05
- Decision: Public 10/hour and 20/day per IP; Studio 60/hour/session; five evaluations/day; five ingestions/day; global 300 generation/evaluation calls/day. Retry network/429/5xx twice only.

### D-027 — UI scope

- Date: 2026-08-05
- Decision: Four core experiences: Dashboard, single-page Agent Workspace, Teacher Review, and Published Agent. Independent brand, not a Bytewise copy.

### D-028 — Brand direction

- Date: 2026-08-06
- Decision: AgentSprout uses deep-ocean navy, blue-green, coral accents, and off-white reading surfaces; youthful but not childish. No Bytewise trademark or implied affiliation.

### D-029 — Device scope

- Date: 2026-08-06
- Decision: Studio desktop-first at 1024 px minimum; Published Agent responsive from 375 px; current Chrome/Edge/Safari and documented accessibility baseline.

### D-030 — Test-provider boundary

- Date: 2026-08-05
- Decision: Runtime/live acceptance uses real OpenAI. Ordinary unit/CI tests may replace only external HTTP responses for deterministic control-flow tests. Live tests are explicit and cost-aware.

### D-031 — CI gate

- Date: 2026-08-05
- Decision: Backend lint/format/type/tests/migration, frontend lint/type/tests/build, Playwright, Docker build, and secret scan must pass. Live workflow is manual.

### D-032 — Vertical module development

- Date: 2026-08-06
- Decision: M1–M8 are frontend/backend vertical slices. A module cannot pass with only backend or only frontend behavior.

### D-033 — Documentation before code

- Date: 2026-08-06
- Decision: Complete all project and M0–M8 development documents first. User review/approval is required before M1 or `.venv` creation.

### D-034 — Context compaction and reuse rule

- Date: 2026-08-05
- Decision: After compaction/resume, reread `AGENTS.md`, current module, and Decision Log. Search/reuse before adding; no unrequired refactor, broad rename, cleanup, or future-module work.

### D-035 — Seed and reset

- Date: 2026-08-05
- Decision: Preserve a fixed published sample and provide an idempotent, admin-secret reset for temporary Studio state. Reset has no ordinary UI.

### D-036 — M1 runtime and package managers

- Date: 2026-08-06
- Decision: Use Python 3.12.13 in `backend/.venv`, Node 24.14.0, and pnpm 11.9.0. Lock direct Python dependencies in `pyproject.toml` plus a generated complete requirements lock, and lock frontend dependencies with `pnpm-lock.yaml`.
- Reason: The system PATH had no Node/npm and only Python 3.9.6; the bundled workspace runtimes provide current isolated versions without modifying the system environment.

### D-037 — M1 persistence details

- Date: 2026-08-06
- Decision: Keep the M1 migration as an infrastructure-only Alembic baseline; each vertical module introduces only the tables it owns. Store citations in a normalized `message_citations` table when M4 adds messages. Set planned Studio sessions to 8 hours and idempotency records to 24 hours when M2 introduces them.
- Reason: Avoid speculative future tables while fixing the two schema/retention choices required by M1.

### D-038 — M1 dependency compatibility and test clients

- Date: 2026-08-06
- Decision: Pin project-local pip to 25.3 for the verified setup. Use `httpx2==2.9.1` for the FastAPI/Starlette test client while retaining Chroma's locked `httpx==0.28.1` transitive dependency; the packages use separate import namespaces. Generate `requirements.lock` from the resolved, tested Python 3.12 environment and verify it with `pip check` and a lockfile install.
- Reason: pip 26.2.1 was incompatible with the available lock-generation tool, and Starlette 1.4.1 explicitly moved its test client to `httpx2` while Chroma 1.5.9 still declares `httpx`.

### D-039 — M2 session, access limiter, and idempotency details

- Date: 2026-08-06
- Decision: Use an opaque `agentsprout_session` cookie backed by an HMAC token hash, with an 8-hour server expiry. Rotate the CSRF token on session restoration and keep the raw CSRF value in frontend memory only. Permit five failed access-code attempts per keyed client-IP hash in 15 minutes. Retain Agent-creation idempotency records for 24 hours and reject key reuse with a different request hash.
- Reason: Implements the approved demo gate without browser-stored credentials, raw IP storage, or ambiguous duplicate creation behavior.

## Open implementation selections that do not change product scope

These are intentionally selected and recorded during the named module:

- M1: exact supported Python/Node/package versions and lockfiles
- M1: exact session/idempotency retention durations within the approved behavior
- M1: normalized citations storage representation in SQLite
- M3: commit original NOAA PDF versus verified download script, after checking file/license/size
- M4: final retrieval threshold calibration using accepted evidence, without exposing it to students
- M8: current Railway/Vercel plan details and costs, rechecked before any billable action

Any selection that changes approved UX, safety, cost boundary, external service, or acceptance behavior requires user confirmation and a new decision entry.
