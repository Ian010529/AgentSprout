# M8 Cloud Acceptance Evidence

## Release identity

- Acceptance IDs: `ACC-DEP-001`, `ACC-DEP-002`, `ACC-CI-001`, `ACC-DEMO-001`, and final M1–M7 regression.
- Accepted date: 2026-08-06 (Asia/Shanghai).
- GitHub repository: <https://github.com/Ian010529/AgentSprout>
- Accepted frontend commit: `8fa75b880529a3c9d6697fdaf289c08459495de1`.
- Railway backend deployment: `3897fb86-d233-4d70-a595-0eb7df710191`; no backend source changed between its accepted source commit and `8fa75b8`.
- Vercel deployment: `dpl_14Nay2au5AGgqct2MGGANmjPQ13n`.
- Frontend: <https://agentsprout.vercel.app>
- Backend readiness: <https://agentsprout-api-production.up.railway.app/api/v1/ready>
- Fixed public sample: <https://agentsprout.vercel.app/p/ocean-explorer>

No access code, API key, session value, admin token, child identity, or raw privacy canary is
recorded in this evidence.

## GitHub and CI

The repository was scanned before publication and after the accepted accessibility correction.
The accepted GitHub Actions run is
<https://github.com/Ian010529/AgentSprout/actions/runs/31080861188>.

Result: backend, frontend, system, and aggregate `ci` jobs all passed. The run covered Ruff,
formatting, Pyright, Pytest, Alembic from empty storage, ESLint, TypeScript, 32 Vitest tests,
Next.js production build, provider-boundary Chromium/WebKit lifecycle, axe, secret/runtime-data
history scan, Docker build, container startup, and volume restart.

## Production configuration

Railway runs one `agentsprout-api` replica with one volume mounted at `/app/data`. SQLite,
Chroma, and uploads resolve under that mount. `/api/v1/ready` returned `ok` for SQLite, Chroma,
uploads, and migrations. Railway CORS returned only the exact
`https://agentsprout.vercel.app` origin.
The final Railway status reported one running instance and a Ready 500 MB volume using about
37.4 MB after both rehearsals and cleanup.

Vercel stores `NEXT_PUBLIC_API_BASE_URL=/api-proxy` and the server-only Railway origin for
Production, Preview, and Development. Browser Studio requests therefore use a same-origin
Secure HttpOnly session path. Both values were persisted at project level and the final
deployment was rebuilt without one-off environment flags.

No paid-plan upgrade or billing mutation was made. The deployment used the existing Vercel
entitlement and Railway trial entitlement; OpenAI remains separately metered.

## First real cloud lifecycle

The first run started from the new production volume and created the fixed Ocean Explorer
sample through Vercel's production proxy.

- NOAA upload: `202`; 13 pages, 48 chunks, checksum
  `029d79e6d17e506cc35d3fb2bdc5b676689fcbfee543df9c340feef0eaeb794c`.
- Upload-to-Ready: about 8.7 seconds from persisted timestamps.
- Grounded chat: 13,174 ms; three validated citations; 1,267 input and 286 output tokens;
  estimated provider cost `$0.00036165`; zero retry.
- Models: `gpt-4o-mini-2024-07-18`, `text-embedding-3-small`, and
  `omni-moderation-latest`.
- Synthetic email privacy test: `BLOCKED` before provider routing.
- Teacher evaluation: 16/16 completed in 69,583 ms; 15 passed, one visible `AGE-01` failure,
  zero infrastructure errors, release eligible.
- Evaluation metrics: grounded 100%, age 5.0, instruction 4.92.
- Evaluation usage: 17,177 input and 3,258 output tokens; estimated cost `$0.0074801`.
- Judge model: `gpt-4.1-mini-2025-04-14`.
- Full create-to-publish lifecycle: 164,639 ms (2 minutes 44.6 seconds).
- The approved version was published as `ocean-explorer` and explicitly marked as the fixed sample.

## Railway restart persistence

Railway restart returned deployment ID `3897fb86-d233-4d70-a595-0eb7df710191`; both direct
Railway and Vercel-proxied readiness were `200` on the first post-command probe at 2,616 ms.

After restart, the same Agent ID, version ID, knowledge-document ID, 48 Chroma chunks, Ready
upload, evaluation run, 16 case results, release eligibility, and published slug remained.
A new public retrieval completed in 7,462 ms with four citations, proving retrieval from the
persisted vector index after process restart.

## Production browser and accessibility

The published Agent passed a real answer/citation flow in desktop Chromium and 375 × 812
WebKit with reduced motion. Both axe scans reported zero violations; the mobile page had no
horizontal overflow and both browser consoles were clean. Reviewed screenshots were stored
only in `/tmp` and contained no secrets or personal data.

The first production Studio axe run found insufficient contrast in small light-surface labels
and an invalid `alert` role on the `main` landmark. Commit `8fa75b8` corrected the colors and
kept assertive announcement semantics without replacing the landmark role. Dashboard,
Reviews, Published, and the published-without-Draft state then each passed with zero axe
violations and zero console errors on the final Vercel deployment.

## Reset and second rehearsal

An admin reset before rehearsal preserved one fixed sample and deleted no other Agent. A
second real lifecycle then created a temporary Agent, uploaded the NOAA source, returned a
four-citation RAG answer in 8,910 ms, blocked a synthetic address, submitted, and ran the same
16-case evaluation.

The second evaluation again completed 16/16 with 15 pass, one failure, zero errors, grounded
100%, age 5.0, instruction 4.92, and release eligibility. It used 17,764 input and 3,600 output
tokens with an estimated cost of `$0.0079331`. The complete reset-to-publish rehearsal took
88,775 ms (1 minute 28.8 seconds), below the five-minute requirement.

Final cleanup deleted the one temporary Agent and preserved the fixed sample. Railway returned
`404` for the temporary slug and `200` for `ocean-explorer`; the Vercel proxy matched after its
documented public metadata cache invalidated. Public metadata uses a maximum 60-second cache,
which is recorded in the README limitations.

## Acceptance result

- `ACC-DEP-001`: passed — HTTPS proxy, one volume/replica, and post-restart SQLite/Chroma/upload/evaluation/publication persistence verified.
- `ACC-DEP-002`: passed — repository/CI scan green; no secret entered into source, browser output, screenshots, or evidence.
- `ACC-CI-001`: passed — accepted GitHub run is green across every required job.
- `ACC-DEMO-001`: passed — two complete real-provider lifecycles were under five minutes; live/repository/architecture/limitations links are in README.

M8 is accepted. The remaining operational handoff is to keep the private secrets private,
monitor OpenAI/Railway quotas before an interview, and recheck plan eligibility before any
commercial or long-lived deployment.
