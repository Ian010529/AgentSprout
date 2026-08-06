# M11 Backend Layer Boundaries Acceptance Evidence

Acceptance ID: `ACC-MOD-002`, regression of `ACC-SAF-001`, `ACC-RAG-001`,
`ACC-EVL-001`, `ACC-PUB-001`, `ACC-PUB-003`, and `ACC-CI-001`

Documentation commit: `5c2e0aa`

Implementation commit: `23f3680`

Environment: macOS, Python 3.12.13 project virtual environment, Node.js 24 runtime,
Next.js 16.3.0, isolated provider-boundary FastAPI server, empty migrated SQLite/Chroma data
directory, Chromium and WebKit

Commands and results:

- `ruff check app tests alembic` — passed
- `ruff format --check app tests alembic` — passed
- `pyright` — 0 errors, 0 warnings
- `pytest` — 44 tests passed
- empty-data `alembic upgrade head` — migrations `0001` through `0007` passed
- frontend `pnpm lint` — passed
- frontend `pnpm typecheck` — passed
- frontend `NEXT_PUBLIC_API_BASE_URL=/api-proxy pnpm test` — 9 files and 34 tests passed
- frontend production `pnpm build` — passed; all eight routes generated
- `python3 scripts/check_repository.py` — passed
- `node backend/tests/run_m7_browser.cjs` against isolated production frontend and
  provider-boundary backend — passed

Boundary evidence:

- No module under `app/services` imports `app.api`; an automated architecture test enforces it.
- `app.api.schemas` and `app.api.errors` preserve class identity through compatibility exports.
- Application contracts and errors are owned by `app.domain.contracts` and `app.domain.errors`.
- Deterministic safety policy is pure in `app.services.chat_safety`.
- Persisted Studio/global model quotas are independent of Chat orchestration in
  `app.services.rate_limits`.
- Chat read projections and phase copy are isolated in `app.services.chat_queries`.
- The Chroma collection identifier is owned by `app.db.vector`; Review and Publication do not
  import Knowledge internals.
- An automated AST import-graph test verifies that backend internal modules remain acyclic.
- `chat.py` decreased from 1,149 to 884 lines while retaining LangGraph nodes, commands, runtime
  persistence, and failure handling.

Browser result:

```json
{"published":true,"chromium_citation":true,"webkit_375":true,"axe_violations":0,"reduced_motion":true,"direct_mutation_denied":true,"rate_limit_state":true,"console_errors":0}
```

Cloud evidence:

- GitHub CI: `https://github.com/Ian010529/AgentSprout/actions/runs/31089562622`
- backend, frontend, provider-boundary browser lifecycle, repository validation, Docker build,
  and container startup/volume-restart all passed
- only GitHub's action-runtime Node.js 20 deprecation annotation was reported; it is not an
  application failure

No API path, schema, error, database model, migration, LangGraph ordering, safety behavior,
retention behavior, lifecycle transition, frontend behavior, or deployment topology changed.

Accepted on 2026-08-06.

