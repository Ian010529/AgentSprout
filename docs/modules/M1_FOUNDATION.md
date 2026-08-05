# M1 — Foundation

## Status

Accepted by the user on 2026-08-06.

## Vertical outcome

A clean clone can create a project-local Python environment, install locked frontend/backend dependencies, migrate an empty SQLite database, start both applications, render the AgentSprout shell, and show backend readiness through the typed API client.

## Prerequisites

- M0 approved.
- Read `AGENTS.md`, `docs/CURRENT_MODULE.md`, this file, and `docs/DECISION_LOG.md`.
- Confirm installed local Node and Python versions before selecting supported versions.

## Frontend scope

- Scaffold Next.js TypeScript application.
- Select and lock supported Node/package-manager versions; prefer the simplest workspace structure.
- Add minimal assistant-ui dependency only if needed by accepted component primitives.
- Implement AgentSprout design tokens and base typography.
- Implement App Shell, route placeholders, global loading/error/not-found boundaries.
- Implement typed API client with safe error normalization and request IDs.
- Render backend `/health` and `/ready` development status without exposing secret configuration.
- Establish test runner, ESLint, TypeScript, and accessibility-test foundation.

## Backend scope

- Create project-local `.venv`; do not alter system Python.
- Scaffold FastAPI application with versioned route prefix.
- Add Pydantic configuration with fail-fast validation.
- Add SQLAlchemy, Alembic, SQLite WAL, and foreign-key setup.
- Add embedded Chroma client initialization and configurable data roots.
- Add structured sanitized logging and request IDs.
- Implement `/health` and `/ready` exactly as contracted.
- Add provider adapter interfaces/configuration without implementing chat/embedding behavior.
- Add startup stale-job hook foundation without domain jobs.
- Create `.env.example` and complete `.gitignore`.

## Data and migrations

- Create only schema needed for M1 infrastructure and the accepted initial domain tables; do not seed product Agents.
- Migration must work from empty database.
- Document selected normalized citation storage representation and idempotency/session retention choices in Decision Log.
- Create data directories only at runtime and keep them gitignored.

## API scope

- `GET /health`
- `GET /ready`

Other routes may exist only as route-level not-found behavior; do not create stub success responses for future features.

## Non-goals

- access-code session
- Agent creation
- file upload/embedding
- OpenAI live call
- LangGraph
- real chat UI
- evaluation/version/public behavior
- Docker/cloud deployment beyond a later-compatible layout

## Automated checks

- backend lint/format/type/unit foundation
- Alembic upgrade from empty temporary database
- SQLite WAL/foreign-key assertions
- Chroma temporary persistence readiness
- frontend lint/type/component foundation
- Next.js production build
- API-client success/error contract test

## Manual verification

1. Follow README from a clean shell.
2. Create/activate `.venv` and install locked backend dependencies.
3. Install locked frontend dependencies.
4. Start backend and frontend.
5. Open the frontend shell and confirm health/readiness UI.
6. Stop/restart backend and confirm the data path remains accessible.
7. Inspect browser console and backend logs for secret/error leakage.

## Acceptance mapping

- `ACC-FND-001`
- `ACC-FND-002`
- relevant parts of `ACC-CI-001`

## Exit gate

- [x] Frontend and backend start through verified README commands.
- [x] Project-local `.venv` exists and system Python is untouched.
- [x] Dependency versions and lockfiles are recorded intentionally; Git commit evidence is added below.
- [x] Empty migration passes, including creation of a previously absent data directory.
- [x] `/health` and `/ready` match API contract.
- [x] App Shell handles loading/readiness/failure/retry states.
- [x] All M1 and M0 documentation regression checks pass.
- [x] No future feature returns fake success.
- [x] Evidence is recorded before `CURRENT_MODULE` moves to M2.

## Acceptance evidence

### ACC-FND-001 — Fresh setup

```text
Acceptance ID: ACC-FND-001
Commit: 949c9d2 (M1 foundation snapshot)
Environment: macOS arm64; Python 3.12.13; Node 24.14.0; pnpm 11.9.0
Commands: README environment creation/install/start commands; backend and frontend quality gates
Result: PASS — backend and frontend started on ports 8000/3000; 7 backend tests and 4 frontend tests passed; lint, format, strict types, and production build passed
Artifact: README.md, backend/requirements.lock, frontend/pnpm-lock.yaml
Notes: no real secret was written; M1 process-scoped synthetic values made zero OpenAI calls
```

### ACC-FND-002 — Persistence and readiness

```text
Acceptance ID: ACC-FND-002
Commit: 949c9d2 (M1 foundation snapshot)
Environment: local temporary data root /tmp/agentsprout-m1-live-20260806
Commands: alembic upgrade/current; API tests; local browser acceptance
Result: PASS — empty migration reached 0001_foundation; SQLite WAL/foreign keys, persistent Chroma, uploads, and migration checks passed
Artifact: backend/tests/test_foundation.py and browser acceptance observations in this section
Notes: browser showed Workshop ready with four ok checks; offline state exposed safe retry; backend restart on the same data root recovered ready; browser console contained zero errors
```

### ACC-CI-001 — M1 subset

```text
Acceptance ID: ACC-CI-001 (M1 subset)
Commit: 949c9d2 (M1 foundation snapshot)
Environment: local locked environments
Commands: ruff check; ruff format --check; pyright; pytest; pnpm lint; pnpm typecheck; pnpm test; pnpm build
Result: PASS — Ruff clean, 0 Pyright errors, 7/7 Pytest, ESLint clean, TypeScript clean, 4/4 Vitest, Next production build successful
Artifact: this module document
Notes: Playwright CI, Docker, cloud, and full product E2E remain owned by later modules
```

### Manual browser observations

- 1440 × 1000 desktop viewport had `scrollWidth == 1440` and no horizontal overflow.
- The deep-ocean AgentSprout shell rendered the Ocean Explorer field-note preview and semantic landmarks.
- `/access` explicitly stated M2 ownership and that M1 does not simulate completed behavior.
- An unknown route rendered the custom privacy-preserving 404.
- Stopping the backend changed the status card to `Backend needs attention` without a console error.
- Restarting the backend with the same SQLite/Chroma data root and selecting `Check again` restored `Workshop ready`.
