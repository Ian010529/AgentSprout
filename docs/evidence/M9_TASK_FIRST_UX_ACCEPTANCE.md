# M9 Task-first UX Acceptance Evidence

## Local implementation

Acceptance ID: `ACC-UX-001`, `ACC-UX-002`, regression of `ACC-PUB-004` and `ACC-CI-001`

Commit: `df65dcd`

Environment: macOS, local Next.js 16.3.0 frontend and accepted FastAPI demo data

Commands and results:

- `pnpm lint` — passed
- `pnpm typecheck` — passed
- `pnpm test -- --run` — 9 files and 32 tests passed
- `pnpm build` — production build passed; all eight routes generated
- `python3 scripts/check_repository.py` — passed
- `node backend/tests/run_m9_browser.cjs` — passed in Chromium 1440 x 1000 and WebKit
  375 x 812 with zero axe violations, zero console errors, no horizontal overflow, and all
  first-viewport/chat-order assertions satisfied

Reviewed artifacts:

- `/tmp/agentsprout-m9-access.png`
- `/tmp/agentsprout-m9-workshop.png`
- `/tmp/agentsprout-m9-reviews.png`
- `/tmp/agentsprout-m9-published.png`
- `/tmp/agentsprout-m9-workspace.png`
- `/tmp/agentsprout-m9-teacher-review.png`
- `/tmp/agentsprout-m9-public-desktop.png`
- `/tmp/agentsprout-m9-public-mobile.png`

Observed result:

- Workshop Agent cards and create action are visible in the first desktop viewport.
- Reviews and Published put their real queue/release surface before explanatory content.
- Workspace exposes Agent context, stage navigation, and the selected form in the first viewport.
- Teacher Review exposes the run action, persisted 16/16 result, release gate, baseline, and the
  beginning of case evidence in the first viewport.
- Published Agent desktop uses chat as the dominant column with the composer above the fold.
- Published Agent mobile orders identity, conversation/composer, then Agent/source details.
- Ocean Explorer remains visible where it is project data; generic workflow labels are Agent-neutral.
- No backend, API, persistence, authorization, runtime, evaluation, or lifecycle behavior changed.

## Cloud verification

Pending push, Vercel deployment, GitHub CI, and live browser smoke at the implementation commit.
