# M8 Local Preparation Evidence

## Scope and status

- Acceptance IDs partially exercised: `ACC-DEP-001`, `ACC-DEP-002`, `ACC-CI-001`,
  `ACC-DEMO-001`, plus the complete M1–M7 regression set.
- Commit: the Git commit containing this evidence.
- Environment: macOS arm64; Python 3.12.13; Node 24.14.0; Docker Desktop;
  fresh temporary SQLite, Chroma, upload roots, and test volume.
- Recorded at: 2026-08-06.
- Status: local preparation passed. Cloud URLs, GitHub-hosted CI, cloud redeploy
  persistence, and platform billing remain unaccepted until explicitly authorized.

## Deterministic quality gates

```text
backend/.venv/bin/ruff check app tests alembic ../scripts/check_repository.py
backend/.venv/bin/ruff format --check app tests alembic ../scripts/check_repository.py
backend/.venv/bin/pyright
backend/.venv/bin/pytest
```

Result: Ruff and formatting passed, Pyright reported 0 errors, and Pytest passed
41 tests. The first full run caught and fixed an accidental global override of the
public metadata cache header; the route's explicit 60-second policy remains intact.

```text
pnpm lint
pnpm typecheck
pnpm test
NEXT_PUBLIC_API_BASE_URL=https://api.example.test pnpm build
```

Result: ESLint and TypeScript passed, Vitest passed 26 tests across 9 files, and
the Next.js 16 production build completed with the same-origin `/api-proxy` rewrite
targeting an HTTPS test backend origin. Production response security headers were
inspected from `next start`; the CSP limited connections to self, and frame, MIME,
referrer, camera, geolocation, and microphone controls were present.
The complete browser lifecycle was then rerun through a real local `/api-proxy`
rewrite rather than direct browser-to-FastAPI calls; it passed in 17.28 seconds with
the same zero-violation/zero-console-error result.

Repository validation result:

```text
Repository validation passed: 169 tracked files, 491 history blobs.
```

The check covers current source and Git-history key signatures, forbidden runtime
paths, the machine-local editable lockfile defect, deployment-contract consistency,
and local Markdown links. GitHub Actions syntax also parsed locally as YAML.

## Docker and persistence

Command: `docker build --tag agentsprout-api:m8-local .`

Result: the Python 3.12.13 image built from the corrected portable lockfile at
approximately 989 MB locally, below Railway Free's 4 GB image limit. A fresh
named volume mounted at `/app/data` automatically migrated to `0007_publish`, seeded
exactly 16 evaluation definitions, and returned all readiness checks as `ok`.
Uvicorn ran as UID 999 rather than root. After `docker restart`, the same migration
revision and 16 persisted definitions remained and readiness passed. The exact
temporary container and volume were removed after verification.

## Browser, responsive, and accessibility

Command: `node backend/tests/run_m7_browser.cjs` against a fresh provider-boundary
test server, with public hourly limit five.

Result in 13.19 seconds:

```json
{"published":true,"chromium_citation":true,"webkit_375":true,"axe_violations":0,"reduced_motion":true,"direct_mutation_denied":true,"rate_limit_state":true,"console_errors":0}
```

The first axe run identified insufficient contrast for small muted text on public
paper surfaces. The public-only muted and eyebrow colors were corrected, then both
desktop Chromium and 375 × 812 WebKit passed with reduced motion and no horizontal
overflow. Runtime screenshots remain at the documented M7 `/tmp` paths and are not
committed.

## Live OpenAI verification and performance

Real-provider RAG result:

- exact models: `gpt-4o-mini-2024-07-18`, `text-embedding-3-small`, and
  `omni-moderation-latest`
- result `ANSWERED` with four validated citations on pages 9, 9, 9, and 11
- 1,267 input and 304 output tokens; estimated cost $0.00037245
- provider time 13,864 ms; complete chat run 14,577 ms; no retry
- PII canary made zero provider calls and was absent from persistence

The chat passed its functional/hard-timeout behavior but missed the warmed 8-second
performance target. This is a recorded demo risk; no canned cache or weaker validation
was introduced to hide it.

Real 16-case Teacher evaluation result:

- exact online/Judge models: `gpt-4o-mini-2024-07-18` and
  `gpt-4.1-mini-2025-04-14`
- 16/16 completed in 41,339 ms with zero infrastructure errors and maximum Judge
  concurrency three
- 15 passed, 1 expected visible AGE evidence-overlap failure; release eligible
- grounded pass rate 100%, age average 5.0, instruction average 4.92
- 17,368 input and 3,466 output tokens; estimated cost $0.0076943
- all privacy cases passed and synthetic PII was absent from persistence

The evaluation is below the two-minute target and provides a genuine failure case for
the interview walkthrough rather than a hard-coded perfect score.

## Remaining cloud gate

The following evidence cannot be produced locally and remains blocking for M8 acceptance:

- green GitHub-hosted CI at the deployed commit
- public repository URL and history review after publication
- Railway/Vercel HTTPS URLs and exact cross-site cookie/CORS behavior
- persistent SQLite/Chroma/upload/evaluation/publication data after Railway redeploy
- production browser console/accessibility checks and live URL runbook rehearsal
- final plan choice and measured cloud cost/cold-start behavior

No GitHub, Vercel, Railway, plan, billing, or cloud-secret state was created or changed
during this local preparation.
