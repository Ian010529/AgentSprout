# M2 — Access and Dashboard

## Status

Accepted on 2026-08-06 under the user's instruction to advance automatically after each module passes acceptance.

## Vertical outcome

A user enters the protected Studio, switches the server-authoritative demo role, creates Ocean Explorer from the Knowledge Explorer template, refreshes, and sees the persisted Draft with correct role/state actions.

## Frontend scope

- `/` concept introduction and independent-demo disclaimer.
- `/access` code form with all UX states.
- Studio App Shell session restoration, expiry handling, sign out, and role switch.
- Student Dashboard template card, agent list, empty state, create form, and duplicate-submit protection.
- Teacher Dashboard review-priority list shell using real data, even if no review items exist.
- Agent card states and next actions from backend authority.
- Workspace Define section sufficient to edit and persist all allowed Draft fields.
- Below-1024 Studio device message and keyboard/focus behavior for these flows.

## Backend scope

- Constant-time access-code validation and limiter.
- Opaque hashed server sessions, CSRF token, expiry, revocation, and role update.
- Exact-origin credentialed CORS and Origin/CSRF validation.
- Agent and v1 Draft creation.
- Draft update allowlist and field validation.
- Agent/version reads filtered by Studio session.
- Server-computed allowed actions.
- Idempotency for Agent creation and relevant mutations.
- Audit events for session role and Agent creation without access-code content.

## Data scope

- `demo_sessions`
- `agents`
- `agent_versions`
- `audit_events`
- `rate_limit_buckets` for access and Studio scopes
- idempotency persistence selected in M1

## API scope

- Studio access/session endpoints
- `GET/POST /studio/agents`
- `GET /studio/agents/{id}`
- `GET/PATCH /studio/versions/{id}`

Do not implement submit, next-version, review, or publish behavior in this module.

## Security checks

- Access code absent from URL, local/session storage, logs, error body, and committed fixtures.
- Cookie and CSRF requirements enforced on direct API calls.
- Browser-only role mutation does not change server permission.
- Unknown/protected Draft fields are rejected.
- HTML/script input is rendered safely as text.

## Automated checks

- access success/failure/rate/expiry tests
- CSRF and exact-origin tests
- Student/Teacher permission matrix for current endpoints
- Agent validation/idempotency/persistence tests
- frontend forms and every network state
- Playwright: access → create → edit → refresh → role switch → sign out

## Manual verification

1. Enter invalid and valid access code.
2. Create Ocean Explorer with required fields.
3. Attempt double submit.
4. Refresh and reopen Draft.
5. Change role through the UI and verify server response.
6. Attempt Teacher-only/client-forged behavior directly and confirm denial.
7. Verify empty/error/session-expired views and browser console.

## Acceptance mapping

- `ACC-AUTH-001`
- `ACC-AUTH-002`
- `ACC-AGT-001`

## Non-goals

- knowledge upload
- chat or OpenAI calls
- version submission/review
- teacher evaluation
- public page

## Exit gate

- [x] Full access/create/refresh flow passes through browser.
- [x] Backend, not UI, enforces session, role, CSRF, lifecycle, and fields.
- [x] All required component states are demonstrable.
- [x] M1 regression suite passes.
- [x] No real access code or raw session/CSRF token leakage is found.
- [x] Evidence is recorded before moving to M3.

## Acceptance evidence

### ACC-AUTH-001 and ACC-AUTH-002 — Access and server-owned session

```text
Acceptance IDs: ACC-AUTH-001, ACC-AUTH-002
Commit: pending M2 snapshot
Environment: local FastAPI/Next.js services; isolated temporary SQLite/Chroma root
Commands: Ruff; Pyright; Pytest; direct API security tests; local browser acceptance
Result: PASS — constant-time generic access denial, five-failure limiter, exact Origin, opaque HttpOnly cookie, CSRF rotation, 8-hour expiry, role mutation, revocation, and 401 restoration behavior passed
Artifact: backend/tests/test_access_dashboard.py, frontend/src/components/access-form.test.tsx
Notes: test-only synthetic credentials were process-scoped; no real secret was written to browser storage, URLs, responses, logs, screenshots, or Git
```

### ACC-AGT-001 — Create, edit, restore, and permissions

```text
Acceptance ID: ACC-AGT-001
Commit: pending M2 snapshot
Environment: Chromium in-app browser against localhost:3000/8000
Commands: API integration suite; Vitest component suite; browser access → create → edit → refresh → role switch → sign out
Result: PASS — Ocean Explorer created once, persisted as Draft, editable allowlist restored after refresh, Teacher view was read-only, protected fields were rejected, and sign out revoked the session
Artifact: backend/tests/test_access_dashboard.py, frontend/src/components/studio-dashboard.test.tsx, frontend/src/components/agent-workspace.test.tsx
Notes: browser acceptance found and fixed an over-broad PATCH payload; a regression test now asserts exactly nine editable fields
```

### M2 quality and browser regression

```text
Backend: Ruff clean; format clean; 0 Pyright errors; 14/14 Pytest
Frontend: ESLint clean; TypeScript clean; 11/11 Vitest; Next.js production build successful
Browser: invalid and valid access, persisted Dashboard, Draft edit/refresh, Teacher role, narrow-screen message, and sign out passed
Security: CSRF/origin/role/idempotency/unknown-field tests passed; script markup rendered as inert textbox text
Console: final clean-browser critical flow contained 0 warnings and 0 errors
Responsive: 900 × 800 showed the intentional below-1024 laptop/landscape message
```
