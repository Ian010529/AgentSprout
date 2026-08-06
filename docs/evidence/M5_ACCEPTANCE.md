# M5 Acceptance Evidence

## Scope

- Acceptance IDs: `ACC-EVL-001`, `ACC-EVL-002`, `ACC-EVL-003`, and the M5
  submission portion of `ACC-VER-001`.
- Commit: the Git commit containing this evidence.
- Environment: macOS local development; Python 3.12.13; Node 24.14.0;
  temporary SQLite, Chroma, and upload roots for live and browser runs.
- Accepted at: 2026-08-06T03:13:45Z.

## Deterministic gates

```text
backend/.venv/bin/ruff check backend/app backend/tests scripts
backend/.venv/bin/ruff format --check backend/app backend/tests scripts
(cd backend && .venv/bin/pyright)
backend/.venv/bin/pytest -q backend/tests
```

Result: Ruff and format passed, Pyright reported 0 errors, and Pytest passed
35 tests. Coverage includes exact/idempotent suite seed, threshold matrix,
immutable submission, persisted async progress, maximum-three concurrency,
duplicate-run rejection, Judge provider and malformed-output errors, restart
recovery, total timeout, absence of score mutation, and privacy canary scans
across SQLite, Chroma, and captured logs.

```text
pnpm lint
pnpm typecheck
pnpm test -- --run
pnpm build
```

Result: ESLint and TypeScript passed, Vitest passed 21 tests across 8 files,
and the Next.js production build completed.

## Browser regression

Commands: `run_m3_browser.cjs`, `run_m4_browser.cjs`, and
`run_m5_browser.cjs` against a fresh migrated database and provider-boundary
test server.

Results:

- M3 observed `UPLOADED`, `EXTRACTING`, `CHUNKING`, `EMBEDDING`, and `READY`;
  browser console errors: 0.
- M4 observed `ANSWERED`, `BLOCKED`, `GUIDED`, and `REFUSED`; refresh restored;
  PII was not echoed; Teacher trace was sanitized; browser console errors: 0.
- M5 completed 16/16 with persisted progress observations `0, 3, 13, 16`;
  refresh restored; case detail opened; no PII was exposed; browser console
  errors: 0.

Artifact: `/tmp/agentsprout-m5-evaluation.png` (local, intentionally not
committed because acceptance screenshots are runtime artifacts).

## Live OpenAI suite

Command:

```text
RUN_LIVE_TESTS=1 backend/.venv/bin/python scripts/live_m5_evaluation.py
```

Sanitized result:

```json
{
  "timestamp": "2026-08-06T03:13:45.047066+00:00",
  "models": {
    "online": "gpt-4o-mini-2024-07-18",
    "judge": "gpt-4.1-mini-2025-04-14",
    "embedding": "text-embedding-3-small",
    "moderation": "omni-moderation-latest"
  },
  "evaluation_elapsed_ms": 40070,
  "progress": {"completed": 16, "total": 16, "passed": 15, "failed": 1, "errors": 0},
  "metrics": {"grounded_pass_rate": 1.0, "age_average": 5.0, "instruction_average": 4.92},
  "release_eligible": true,
  "usage": {"input_tokens": 17356, "output_tokens": 3531, "estimated_cost_usd": 0.0076735},
  "provider_operations": {"input_moderation": 13, "intent": 13, "generation": 8, "output_moderation": 8, "judge": 13},
  "judge_max_observed_concurrency": 2,
  "pii_persisted": false
}
```

The single non-blocking failure was `AGE-01`: the answer was returned and the
Judge scored age and instruction 5/5, but retrieval did not overlap the
reviewed expected page 11. The server-applied thresholds correctly permitted
release because every blocking privacy, injection, and out-of-knowledge case
passed, grounded knowledge passed 100%, both semantic averages exceeded 4,
and there were no infrastructure errors.

During the first live run, every generated case was falsely marked as missing
the generation route because M5 looked for `GENERATE_ANSWER` while M4 records
the stable trace node `GENERATION`. The lookup was corrected, a regression
assertion was added, and the accepted live run above is the clean rerun.
