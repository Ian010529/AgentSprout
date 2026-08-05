# Deployment Plan

## 1. Deployment boundary

Cloud deployment occurs only in M8 after local M1–M7 acceptance passes. M0 documentation does not create accounts, repositories, secrets, services, volumes, or billable resources.

## 2. Target topology

| Component | Platform | Persistence |
|---|---|---|
| Next.js frontend | Vercel | build artifact only |
| FastAPI backend | Railway, one replica | Railway volume |
| SQLite | `/app/data/app.db` | Railway volume |
| ChromaDB | `/app/data/chroma` | Railway volume |
| uploads | `/app/data/uploads` | Railway volume |
| source control and CI | GitHub | Git history and Actions artifacts |

## 3. GitHub repository

- Public repository only after secret/runtime-data scan passes.
- Default branch protection should require CI where available.
- `.gitignore` must exclude:
  - `.env*` except `.env.example`
  - backend `.venv`
  - frontend dependency/build directories
  - `data/`, SQLite journals, Chroma persistence, uploads
  - local logs, traces, test videos, unreviewed screenshots
- README includes architecture, local setup, license/source attribution, limitations, repository URL, and live URL.
- Do not commit provider keys to make a fork "work immediately."

## 4. Vercel frontend

### Planned settings

- Root directory: frontend application directory selected in M1.
- Production build uses the committed lockfile.
- Environment variable: `NEXT_PUBLIC_API_BASE_URL` only.
- Production URL is added exactly to backend `ALLOWED_ORIGINS`.
- Preview URLs do not automatically receive credentialed Studio access. Add a specific preview origin only when intentionally testing it.

### Required checks

- production build succeeds locally and in Vercel
- no secret exists in environment values exposed to Next.js client code
- `/p/:slug` renders directly and after browser refresh
- client API failures show documented states
- source maps/build artifacts contain no secret or access code

## 5. Railway backend

### Planned settings

- Deploy from the GitHub backend directory using a committed Dockerfile.
- Bind to `0.0.0.0` and Railway's supplied port.
- One replica only.
- Persistent volume mounted at `/app/data`.
- Health endpoint: `/health`.
- Readiness endpoint checked after migration/startup: `/ready`.
- Restart policy must not create two active volume-mounted replicas.

### Required secrets

- `OPENAI_API_KEY`
- `STUDIO_ACCESS_CODE`
- `ADMIN_RESET_TOKEN`
- `SESSION_SECRET`

### Required non-secret configuration

- `APP_ENV=production`
- `DATA_DIR=/app/data`
- exact `ALLOWED_ORIGINS`
- pinned model IDs
- rate/retention/timeout values from `docs/ARCHITECTURE.md`

Secrets are entered by the user in Railway. They are never pasted into chat or committed.

## 6. Local environment

- M1 creates a project-local backend `.venv`.
- Never install backend packages into system Python.
- `.env.example` documents names and safe placeholders.
- The user creates `.env` locally and enters the real OpenAI key and generated local secrets.
- Local runtime paths point to a gitignored project data directory.
- Docker is not required for ordinary local development.

Exact verified commands are added in M1 after the scaffold exists; documentation must not claim an untested command works.

## 7. Docker boundary

- Docker is required for reproducible Railway backend deployment, not for local development.
- Image uses a supported Python runtime pinned in M1.
- Run as a non-root user when compatible with Railway volume permissions; document any platform-required exception.
- Copy dependency metadata before source for cache efficiency.
- Do not bake `.env`, data, NOAA runtime upload, SQLite, or Chroma files into the image.
- Startup runs safe migrations before serving readiness.
- Health check does not call OpenAI.

## 8. Cookie, CORS, and CSRF deployment

Because Vercel and Railway use different sites by default:

- Studio cookie is Secure and HttpOnly with the required cross-site SameSite setting.
- Backend enables credentialed CORS only for exact production frontend origin.
- All Studio mutations require a session-bound CSRF token in `X-CSRF-Token`.
- Backend validates Origin on credentialed mutation requests.
- Public requests do not require cookies.

If custom domains later place both services under one site, simplify only through a documented decision; do not silently change cookie security.

## 9. Persistent volume verification

Before announcing the live URL:

1. Create a temporary Agent.
2. Upload and finish a small knowledge document.
3. Complete a chat and an evaluation result.
4. Record IDs/checksums without content secrets.
5. Redeploy the backend.
6. Verify Agent, Ready document, Chroma retrieval, and evaluation remain accessible.
7. Verify `/ready` after restart.
8. Remove the temporary test data through the documented reset path.

## 10. Seed and reset

- Startup applies migrations and idempotently seeds the 16 evaluation definitions.
- The fixed public sample is created by an explicit documented seed operation in M7/M8, not duplicated on every startup.
- Admin reset removes temporary Studio state while preserving the fixed sample.
- Seed/reset operations record sanitized counts and audit IDs.
- Reset secrets never appear in README commands as literal values; commands read environment variables.

## 11. Deployment order

1. Verify local CI-equivalent checks.
2. Create/connect GitHub repository after user confirmation.
3. Create Railway backend and persistent volume.
4. Enter Railway secrets and deploy backend.
5. Verify `/health` and `/ready`.
6. Create Vercel frontend and set public API URL.
7. Add exact Vercel production origin to Railway configuration and redeploy.
8. Run cloud vertical smoke tests.
9. Run persistence redeploy test.
10. Seed the fixed public sample.
11. Run public/mobile and Studio E2E.
12. Add final live/repository URLs to README.

## 12. Cost and availability notes

- Railway free/trial resources and persistent-volume limits may change; recheck official platform terms during M8.
- Supabase is not part of the approved architecture.
- Vercel contains no persistent backend state.
- OpenAI quotas remain enforced even if platform traffic is free.
- The user must be told before any plan upgrade or billable platform action.
- Platform cold starts and demo availability are checked on the interview day.

## 13. Rollback and recovery

- Code rollback must not run destructive down-migrations automatically.
- Before a schema-changing deployment, create the platform-supported volume backup or an explicit database/file backup appropriate to demo data.
- If readiness fails after deploy, restore the prior code deployment and keep the volume mounted.
- If a migration partially fails, stop serving readiness and follow its documented recovery; do not recreate the volume.
- Fixed sample data can be recreated only by the idempotent seed path, not by a hidden hard-coded UI fallback.

## 14. Interview-day checklist

- Live URLs respond.
- Railway service is awake and `/ready` passes.
- OpenAI account has sufficient credits/quota.
- Rate buckets leave Studio and public headroom.
- Fixed sample and reset behavior are intact.
- NOAA source is Ready and retrievable.
- One live normal answer and one privacy block pass.
- Evaluation can start and progress.
- GitHub CI is green at the deployed commit.
- Access code is shared privately with the interviewer, not posted publicly.

