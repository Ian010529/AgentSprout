# AgentSprout Studio

> Students build. Teachers evaluate. Safe agents get published.

AgentSprout Studio is an independent interview concept demo for a child-safe agent-building workflow. Students define and test a knowledge-grounded agent, teachers run reproducible evaluations, and only approved versions can be published.

This project is inspired by publicly described needs in AI education and a public AI Software Engineer job description. It is not affiliated with, endorsed by, or produced by Bytewise Coding. No Bytewise trademarks, logos, course assets, or private materials are used.

## Current status

**M8: Cloud Deployment and Product Polish** is in progress. M1–M7 are accepted, and the local vertical demo covers
Studio access, Agent creation, real ingestion/RAG, child-safety routes, the 16-case Teacher
evaluation, immutable v1/v2 comparison, approval, publishing, anonymous public chat, and
reset protection. Production Docker, deployment configuration, repository validation, and
GitHub workflows are locally verified; live GitHub/Vercel/Railway acceptance still requires
explicit account and cost authorization. See
[`docs/CURRENT_MODULE.md`](docs/CURRENT_MODULE.md).

## Five-minute demo outcome

1. Enter the protected Studio.
2. Create **Ocean Explorer** from the Knowledge Explorer template.
3. Define the problem, intended users, success goal, audience age, and response behavior.
4. Upload NOAA's CC0 *Ocean Literacy* PDF.
5. Ask a grounded question and inspect page-level citations.
6. Demonstrate out-of-knowledge refusal, privacy blocking, homework guidance, and prompt-injection resistance.
7. Submit a version for teacher review.
8. Run 16 fixed evaluation cases and inspect failures, latency, token use, and traces.
9. Create v2 with a required change reflection and compare it with v1.
10. Approve and publish the passing version to a mobile-friendly public page.

## Stack

- Frontend: Next.js 16, TypeScript, React 19, and selected assistant-ui conversation primitives
- Backend: Python 3.12, FastAPI, and a typed LangGraph runtime
- Business data: SQLite
- Vector data: embedded persistent ChromaDB
- Models: OpenAI Responses, Embeddings, and Moderation APIs
- Planned hosting: Vercel frontend; Railway backend with a persistent volume

Direct backend versions live in [`backend/pyproject.toml`](backend/pyproject.toml), the complete Python environment is frozen in [`backend/requirements.lock`](backend/requirements.lock), and frontend packages are locked in [`frontend/pnpm-lock.yaml`](frontend/pnpm-lock.yaml).

## Local setup

Required versions:

- Python 3.12.x (verified with 3.12.13)
- Node 24.x (verified with 24.14.0)
- pnpm 11.9.0

Create the project-local Python environment from the repository root. These commands do not modify system Python:

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade "pip==25.3"
backend/.venv/bin/python -m pip install -r backend/requirements.lock
backend/.venv/bin/python -m pip install -e backend --no-deps
```

Install the frontend from its lockfile:

```bash
cd frontend
pnpm install --frozen-lockfile
cd ..
```

Copy the environment template and replace every placeholder. Keep the resulting `.env` local. M1 does not spend OpenAI tokens, but startup intentionally fails if required provider and session configuration is absent.

```bash
cp .env.example .env
```

Migrate the SQLite database from an empty data directory:

```bash
cd backend
.venv/bin/alembic upgrade head
cd ..
```

Start the backend in one terminal:

```bash
cd backend
.venv/bin/uvicorn app.main:create_app --factory --reload --port 8000
```

Start the frontend in another terminal:

```bash
cd frontend
pnpm dev
```

Open <http://localhost:3000>. The development status card calls the real readiness endpoint and reports SQLite, Chroma, uploads, and migration state. Direct API checks are available at:

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/ready
```

## Quality checks

```bash
cd backend
.venv/bin/ruff check app tests alembic
.venv/bin/ruff format --check app tests alembic
.venv/bin/pyright
.venv/bin/pytest

cd ../frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

No `.env`, API key, access code, runtime database, vector data, upload, or log belongs in Git.

CI additionally runs the complete provider-boundary browser lifecycle in Chromium and
mobile WebKit, axe accessibility checks, an empty migration, Git history/runtime-data scans,
Docker build/start/restart checks, and documentation-link validation. Real OpenAI smoke tests
are a separate manually dispatched workflow so ordinary pushes do not spend provider tokens.

## Production container

Build the same backend image used by Railway from the repository root:

```bash
docker build --tag agentsprout-api:local .
```

The entrypoint migrates the mounted database before startup and runs the application as an
unprivileged user. Production requires one persistent volume at `/app/data`, one backend
replica, exact HTTPS CORS origin configuration, and secrets entered outside Git. See the
[deployment plan](docs/DEPLOYMENT.md) for the verified Railway/Vercel settings, current plan
limits, and cost boundary.

Production browser traffic uses Vercel's same-origin `/api-proxy` rewrite to Railway so the
Studio session does not depend on third-party cookie acceptance. Local development continues
to call the backend directly.

## Documentation map

- [Product requirements](docs/PRD.md)
- [UX and frontend behavior](docs/UX_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [API contracts](docs/API_CONTRACTS.md)
- [Security and privacy](docs/SECURITY_AND_PRIVACY.md)
- [Test strategy](docs/TEST_STRATEGY.md)
- [Acceptance tests](docs/ACCEPTANCE_TESTS.md)
- [Deployment plan](docs/DEPLOYMENT.md)
- [Demo runbook](docs/DEMO_RUNBOOK.md)
- [Decision log](docs/DECISION_LOG.md)
- [Module plans](docs/modules/)

## Knowledge source

The example knowledge base is NOAA's accessible 2024 *Ocean Literacy: The Essential
Principles and Fundamental Concepts of Ocean Sciences for Learners of All Ages*. NOAA
identifies the document as CC0 Public Domain. Download the unchanged, checksum-locked file
with `python scripts/download_noaa_source.py`; the complete verification record is in
[`docs/KNOWLEDGE_SOURCE.md`](docs/KNOWLEDGE_SOURCE.md).

Source: <https://repository.library.noaa.gov/view/noaa/67228>

## Planned live demo

The final README will include the GitHub repository URL and Vercel live URL after M8 deployment. Studio access will require a separately shared access code. The published Ocean Explorer page will be public but rate limited.

For the local interview path, publish with slug `ocean-explorer`, then open
<http://localhost:3000/p/ocean-explorer>. After confirming that publication, protect this
single canonical sample from demo resets with the admin-only seed operation:

```bash
curl -X POST \
  -H 'X-Admin-Reset-Token: <ADMIN_RESET_TOKEN>' \
  http://localhost:8000/api/v1/admin/seed-fixed-sample/<AGENT_ID>
```

Public prompts and validated answers are held only in backend process memory for ten
minutes. SQLite retains content-free run usage/safety metadata, and public requests are
independently rate limited from Studio chat.
