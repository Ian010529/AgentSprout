# M4 — Safe Playground and LangGraph Runtime

## Status

Pending M3 acceptance.

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

- [ ] Real normal and safety browser flows pass.
- [ ] PII no-provider/no-persistence canary evidence passes.
- [ ] Output is validated before display.
- [ ] Citations are real and version-filtered.
- [ ] Teacher trace is useful and sanitized.
- [ ] Normal latency is measured against target.
- [ ] M1–M3 regressions pass.
- [ ] Evidence is recorded before moving to M5.

