# M6 Acceptance Evidence

## Scope

- Acceptance IDs: `ACC-VER-001`, `ACC-VER-002`, and the request-change/approval
  portions of `ACC-REV-001`.
- Commit: the Git commit containing this evidence.
- Environment: macOS local development; Python 3.12.13; Node 24.14.0; fresh
  migrated temporary SQLite, Chroma, and upload roots.
- Accepted at: 2026-08-06.

## Deterministic gates

```text
backend/.venv/bin/ruff check backend/app backend/tests backend/alembic/versions
backend/.venv/bin/ruff format --check backend/app backend/tests backend/alembic/versions
(cd backend && .venv/bin/pyright)
backend/.venv/bin/pytest -q backend/tests
```

Result: Ruff and format passed, Pyright reported 0 errors, and Pytest passed
37 tests. M6 coverage includes feedback/reflection validation, immutable v1,
idempotent monotonic v2 creation, distinct Ready document/vector metadata,
zero new embedding calls, unchanged upload quota, comparison baseline rejection,
wrong-run approval rejection, release-gated approval, and persisted reviews.

```text
pnpm lint
pnpm typecheck
pnpm test -- --run
pnpm build
```

Result: ESLint and TypeScript passed, Vitest passed 23 tests across 8 files,
and the Next.js production build completed.

## Browser acceptance

Command: `node backend/tests/run_m6_browser.cjs` against a fresh migration and
provider-boundary test server.

Result:

```json
{"requested_changes":true,"v1_immutable":true,"v2_created":true,"reflection_visible":true,"compared":true,"approved":true,"console_errors":0}
```

The browser executed v1 submit/evaluate, persisted Teacher feedback, Student
reflection, isolated v2 creation, v2 submit/evaluate, same-baseline comparison,
and eligible approval. The screenshot was visually reviewed at
`/tmp/agentsprout-m6-comparison.png`; the approved state is at
`/tmp/agentsprout-m6-approved.png`. Runtime screenshots are intentionally not
committed.

## Regression

- M3 browser stages: `UPLOADED`, `EXTRACTING`, `CHUNKING`, `EMBEDDING`, `READY`;
  console errors 0.
- M4 browser results: `ANSWERED`, `BLOCKED`, `GUIDED`, `REFUSED`; refresh,
  privacy non-echo, and sanitized trace passed; console errors 0.
- M5 browser: 16/16 persisted, progress observations `0, 3, 9, 16`, refresh
  restored, evidence detail opened, no PII exposed, console errors 0.

The first combined regression exposed that copied v2 document rows were counted
as uploads by the pre-M6 daily ingestion query. The query now counts distinct
documents that have an `ingestion_job`; the zero-embedding v2 snapshot consumes
neither provider calls nor upload quota, and the M5 rerun then passed.
