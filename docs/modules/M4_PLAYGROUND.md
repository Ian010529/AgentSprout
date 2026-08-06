# M4 — Safe Playground and LangGraph Runtime

## Status

Accepted on 2026-08-06.

## Vertical outcome

From the browser, a Student can receive a real grounded NOAA answer with citations and demonstrate all five safety/knowledge routes. Only complete validated output is displayed, and a Teacher can inspect a sanitized trace.

## Frontend scope

- Workspace Test section using reusable assistant-ui conversation primitives.
- Studio conversation restoration after refresh.
- Backend-reported processing stages; no token streaming or fake timers.
- Final answer/result types and citation chips/detail.
- Safety-example buttons for knowledge boundary, PII, homework, and injection.
- Moderation, timeout, rate, provider, validation, and retry states.
- Student simplified result view.
- Teacher-only trace drawer reachable through accepted Studio flow.
- Disable duplicate sends and unsafe retry semantics.

## Backend scope

- LangGraph state and nodes from `docs/ARCHITECTURE.md`.
- Deterministic email/phone/address pre-provider guard.
- Input/output OpenAI Moderation integration.
- Structured intent classification for ordinary, homework, and injection routes.
- Retrieval and deterministic out-of-knowledge branch.
- Structured online answer generation with pinned snapshot.
- Age-mode and response-length policy.
- Citation allowlist/schema validation.
- Discard raw unsafe/invalid output.
- Persist allowed Studio conversations only.
- Public behavior is not exposed yet.
- Persist sanitized run/node/safety traces, usage, latency, retry, and estimated cost.
- Studio and global call limits.

## Data scope

- `studio_conversations`
- `messages` and citations
- `chat_runs`
- `run_node_traces`
- `safety_events`
- provider/rate usage fields

## API scope

- Studio run create/status
- Studio conversation read
- Teacher trace read

Submit/review/public endpoints remain out of scope.

## Safety fixture rules

- PII uses synthetic unique canaries only.
- Fixed UI example labels may fill prompts, but results always come from backend execution.
- Blocked PII POST performs no provider call and persists no raw input.
- Raw unsafe output exists only in the provider adapter response scope long enough to validate/discard.

## Retrieval calibration

- Begin with documented threshold.
- Evaluate known NOAA and clearly unsupported queries.
- Change threshold only with recorded evidence and Decision Log entry.
- Do not tune on a single hand-picked success case.

## Automated checks

- LangGraph branch and stop-node tests
- PII canary no-call/no-persistence suite
- moderation input/output behavior
- homework age-mode behavior
- injection non-disclosure
- low-retrieval no-generation assertion
- structured output/citation validation and malformed response
- timeout/429/5xx retry policy
- Studio retention fields and trace allowlist
- component state/accessibility tests
- Playwright normal + five route flows
- opt-in real generation/moderation smoke tests

## Manual verification

1. Ask one known NOAA question and inspect page citation.
2. Ask a clearly unsupported question.
3. Send synthetic PII and inspect sanitized trace/provider no-call evidence.
4. Send homework and injection prompts.
5. Exercise a moderation route in controlled test mode.
6. Refresh and restore normal Studio conversation.
7. Inspect Teacher trace for exact nodes and absence of secrets/PII.
8. Measure normal answer latency and browser console.

## Acceptance mapping

- `ACC-SAF-001` through `ACC-SAF-004`
- `ACC-RAG-001`, `ACC-RAG-002`
- `ACC-OBS-001`

## Non-goals

- evaluation suite/Judge
- version submit/review
- public chat
- model escalation or token streaming
- external observability service

## Exit gate

- [x] Real normal and safety browser flows pass.
- [x] PII no-provider/no-persistence canary evidence passes.
- [x] Output is validated before display.
- [x] Citations are real and version-filtered.
- [x] Teacher trace is useful and sanitized.
- [x] Normal latency is measured against target.
- [x] M1–M3 regressions pass.
- [x] Evidence is recorded before moving to M5.

## Acceptance evidence

Recorded on 2026-08-06:

- Live provider: `RUN_LIVE_TESTS=1 backend/.venv/bin/python scripts/live_m4_smoke.py`
  completed the real NOAA upload, embeddings, retrieval, structured grounded generation,
  input/output Moderation, and Teacher trace flow at
  `2026-08-06T02:33:05.867253+00:00`. It used the pinned
  `gpt-4o-mini-2024-07-18`, `omni-moderation-latest`, and
  `text-embedding-3-small` models. The answer was `ANSWERED` with three validated page-9
  citations; 1,267 input and 245 output tokens cost an estimated USD 0.00033705.
- Privacy: the live synthetic-email branch made zero provider calls and its canary was not
  present in SQLite. Deterministic integration coverage repeats no-call/no-persistence
  checks for email, phone, and detailed-address canaries and scans SQLite and Chroma.
- Latency: the normal real chat run took 11,697 ms, including 600 ms retrieval and
  11,048 ms provider time with zero retries. This exceeds the warmed 8-second target but
  remains within the documented 20-second provider hard timeout. The target is a reported
  performance objective rather than a safety/release gate; no fake delay, cache, fallback,
  or model substitution was used.
- Browser: the provider-boundary Playwright flow exercised a grounded answer and citation,
  knowledge-boundary refusal, privacy block, homework guidance, injection refusal, input
  moderation, refresh restoration, and the Teacher-only sanitized trace. It observed result
  types `ANSWERED`, `BLOCKED`, `GUIDED`, and `REFUSED`, with no PII echo and zero console
  errors. Reviewed screenshots were written only to `/tmp`.
- Backend: Ruff format and lint passed; Pytest passed 27 tests; Pyright reported zero errors;
  `pip check` reported no broken requirements. Tests cover LangGraph branches, exact
  retrieved-citation allowlists, malformed output, provider failure/restart recovery,
  idempotency, rate boundaries, and Studio retention/authorization.
- Frontend: ESLint and TypeScript passed; Vitest passed 19 tests across 7 files; the Next.js
  production build completed successfully. The UI uses assistant-ui external-store
  primitives while the backend remains authoritative for messages and processing phases.
- Regression and repository hygiene: the M3 browser flow again observed all five ingestion
  stages with zero console errors. Empty-database migration through `0004_playground`,
  `git diff --check`, ignored-file checks, tracked runtime-data checks, and the OpenAI
  key-pattern scan passed before transition.
