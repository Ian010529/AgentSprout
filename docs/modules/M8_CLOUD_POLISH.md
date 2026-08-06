# M8 — Cloud Deployment and Product Polish

## Status

In progress after M7 acceptance on 2026-08-06. Local preparation may proceed; GitHub and
cloud account mutations remain blocked until the user explicitly authorizes them.

Local Docker, CI configuration, repository scanning, accessibility, browser regression,
and real-provider evidence are recorded in
[`docs/evidence/M8_LOCAL_PREPARATION.md`](../evidence/M8_LOCAL_PREPARATION.md).

## Vertical outcome

The accepted local product is deployed from a public GitHub repository to Vercel and a single-volume Railway backend, survives redeploy, passes CI/cloud E2E and accessibility checks, and supports a repeatable five-minute interview demonstration.

## Prerequisites

- All local M1–M7 acceptance evidence complete.
- User explicitly authorizes GitHub/cloud account actions and any cost.
- Recheck current official Vercel/Railway limits and pricing.
- User enters secrets directly into platform settings.

## Frontend scope

- Final visual consistency across Access, Dashboard, Workspace, Teacher Review, and Published Agent.
- Complete loading/empty/success/error/timeout/rate/disabled/retry states.
- Studio desktop-width behavior and Published Agent mobile behavior.
- Keyboard/focus/live-region/contrast/reduced-motion verification.
- Production API URL/cookie/CORS behavior.
- Reviewed acceptance screenshots without PII/secrets.
- README live/repository links and independent-concept disclaimer.

## Backend scope

- Production Dockerfile and startup/readiness behavior.
- Railway one-replica configuration and `/app/data` volume.
- Production secrets/config and exact CORS origin.
- Migration/startup stale-job/retention behavior in cloud.
- Health/readiness monitoring.
- Persistence redeploy test.
- Seed/reset in production demo environment.
- No functional redesign or broad refactor; only defects required for documented acceptance.

## CI/CD scope

- GitHub Actions checks from `docs/TEST_STRATEGY.md`.
- Secret and runtime-data scanning.
- Docker build.
- Manual live smoke workflow requiring explicit secret/config.
- Vercel and Railway deploy from the accepted Git commit.
- Deployment URLs and commit recorded in acceptance evidence.

## Cloud verification

1. Deploy backend and volume.
2. Enter secrets privately.
3. Verify health/readiness and migrations.
4. Deploy frontend and configure exact origins.
5. Run core cloud E2E.
6. Upload, chat, evaluate, approve, and publish temporary Agent.
7. Redeploy backend.
8. Verify SQLite, Chroma, upload, evaluation, and public Agent persistence.
9. Reset temporary workspace and verify fixed sample.
10. Run mobile/public WebKit flow.
11. Run live smoke and capture models/latency/usage.

## Performance and demo scope

- Measure normal chat, NOAA ingestion, and 16-case evaluation against targets.
- Document platform cold-start behavior honestly.
- Execute `docs/DEMO_RUNBOOK.md` twice: once from reset and once as interview rehearsal.
- Record total time and any prepared-state assumption.
- Do not introduce caches containing canned answers to meet timing.

## Automated checks

- full local CI suite
- cloud Playwright core flow
- Chromium full, WebKit/mobile public critical flow
- production browser console check
- build/source secret scan
- direct public authorization probes
- persistence redeploy assertions
- link/document validation

## Acceptance mapping

- `ACC-DEP-001`
- `ACC-DEP-002`
- `ACC-CI-001`
- `ACC-DEMO-001`
- final regression of every prior acceptance ID

## Non-goals

- changing storage providers
- horizontal scaling
- production child rollout
- new product features
- custom domain purchase
- paid-plan upgrade without explicit user approval

## Exit gate

- [ ] GitHub CI is green at deployed commit.
- [ ] Public repository contains no secrets/runtime data.
- [ ] Vercel and Railway URLs pass health and E2E.
- [ ] Persistent data survives backend redeploy.
- [ ] All four experiences and required states are visually/accessibly accepted.
- [ ] Full live model smoke passes.
- [ ] Five-minute runbook is rehearsed and timed.
- [ ] README contains verified setup, architecture, limitations, and links.
- [ ] All M1–M7 regressions and final acceptance IDs pass.
- [ ] Final evidence is recorded and user receives deployment/secret/cost handoff.
