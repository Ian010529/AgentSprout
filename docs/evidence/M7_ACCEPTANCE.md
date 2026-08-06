# M7 Acceptance Evidence

## Scope

- Acceptance IDs: publication/withdrawal portion of `ACC-REV-001`, `ACC-PUB-001`
  through `ACC-PUB-004`, and `ACC-OPS-001`.
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

Result: Ruff and format passed, Pyright reported 0 errors, and Pytest passed 40
tests. M7 cases cover Approved-only publication, slug syntax/collision and atomic
pointer behavior, publish/withdraw idempotency, public DTO field allowlisting,
run-token isolation and expiry, pre-provider public PII blocking, prompt/answer
non-persistence, restart-persistent public limiting, independent Studio allowance,
explicit fixed-sample seeding, secure reset, and reset replay.

Both empty migration and `0006_versions_review` → `0007_publish` upgrade paths passed.

```text
pnpm lint
pnpm exec tsc --noEmit
pnpm test -- --run
pnpm build
```

Result: ESLint and TypeScript passed, Vitest passed 26 tests across 9 files, and
the Next.js 16 production build completed with `/p/[slug]` as a dynamic route.

## Browser acceptance

Command: `node backend/tests/run_m7_browser.cjs` against a fresh migration and
provider-boundary test server with the public hourly limit set to five.

Result:

```json
{"published":true,"chromium_citation":true,"webkit_375":true,"direct_mutation_denied":true,"rate_limit_state":true,"console_errors":0}
```

The browser created and ingested Ocean Explorer, submitted, ran the 16-case suite,
approved, confirmed publication, opened the public slug in Chromium, displayed a
validated answer and page citations, received `401` for an anonymous Studio mutation,
completed the critical chat flow in WebKit at 375 × 812 without horizontal overflow,
and displayed the expected public `429` retry state.

Visually reviewed runtime artifacts (intentionally not committed):

- `/tmp/agentsprout-m7-public-desktop.png`
- `/tmp/agentsprout-m7-public-mobile.png`
- `/tmp/agentsprout-m7-public-limit.png`

## Persistence inspection

The accepted browser database contained five sanitized `PUBLIC` runs, zero messages
joined to public runs, zero node traces joined to public runs, and two persistent public
rate buckets (hour/day). Recursive binary search across SQLite, Chroma, and uploads found
no public PII canary. Unit acceptance additionally used unique public-only prompt and
answer canaries and verified both were absent from SQLite bytes after completion.

## Regression

The complete backend suite includes all M1–M6 tests and passed after M7. Frontend tests
retain access, Dashboard, Workspace, knowledge, Playground, evaluation, and version-review
coverage. M6's accepted browser evidence remains unchanged; the M7 browser flow starts from
a fresh database and replays create → ingest → submit → evaluate → approve before publish.
