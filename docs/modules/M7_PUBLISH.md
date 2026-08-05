# M7 — Publish and Public Agent

## Status

Pending M6 acceptance.

## Vertical outcome

The Teacher publishes an Approved version to a stable public slug. Anonymous visitors can use a responsive, rate-limited, privacy-minimizing Agent, while all Studio internals and mutations remain inaccessible. The demo workspace can be safely reset without removing the fixed sample.

## Frontend scope

- Teacher Publish and Withdraw actions with confirmation and conflict states.
- Public `/p/:slug` page with allowlisted project metadata, Approved badge, version, NOAA attribution, welcome message, privacy reminder, chat, citations, and rate/failure states.
- Mobile-responsive behavior from 375 px.
- No Studio navigation/config/trace/evaluation data in public UI.
- Public short-lived run-token polling.
- Fixed public sample discoverable from README/final demo path.

## Backend scope

- Publish eligibility/state/role checks and atomic active-public-version pointer.
- Stable unique slug validation/conflict behavior.
- Withdraw behavior.
- Public metadata DTO allowlist.
- Public LangGraph run using the accepted M4 runtime and published immutable version.
- Public prompt/result held only in process memory; persist sanitized metadata only.
- Public run token, expiry, and result isolation.
- Per-IP hourly/daily, public/global quotas with keyed IP hash.
- Independent Studio allowance.
- Public request Origin/abuse controls appropriate to unauthenticated access.
- Fixed sample seed operation.
- Admin-secret reset preserving fixed sample.
- Cascading cleanup of temporary SQLite/Chroma/files.

## Data scope

- agent published-version pointer and slug
- publish/withdraw reviews/audit
- public run sanitized metadata
- rate-limit buckets
- reset/maintenance audit
- fixed-sample marker selected safely in implementation

## API scope

- publish and withdraw
- public metadata
- public run create/status with run token
- admin reset and maintenance endpoints

## Public retention rules

- Do not write full public input/output into SQLite, Chroma, logs, or traces.
- Sanitized result category, usage, latency, limiter, and safety event may persist.
- In-memory result expires and becomes unavailable after the documented short-lived window.
- A service restart marks active public run failed; it does not reconstruct content from storage.

## Automated checks

- approval/publish/withdraw transition and idempotency
- slug validation/conflict and pointer atomicity
- old published version remains until replacement publish succeeds
- public DTO snapshot/field allowlist
- Studio API and trace/evaluation access denial
- public run-token isolation/expiry
- public full-content non-persistence search
- limiter persistence/restart and independent Studio budget
- reset deletion across stores and fixed-sample preservation
- public component states/accessibility/responsive tests
- Playwright publish → public chat/citation → direct mutation denial → limit state
- WebKit and 375 px public critical flow

## Manual verification

1. Attempt to publish failing/unapproved version.
2. Publish approved version and open slug in private browser.
3. Chat and inspect citation.
4. Search public API payloads/storage for Studio-only fields/full content.
5. Exercise rate-limit behavior in controlled test.
6. Publish replacement and verify pointer behavior.
7. Withdraw and verify unavailable state.
8. Seed fixed sample, create temporary workspace data, reset, and verify only temporary data is removed.

## Acceptance mapping

- publish/withdraw part of `ACC-REV-001`
- `ACC-PUB-001` through `ACC-PUB-004`
- `ACC-OPS-001`

## Non-goals

- public accounts/history
- social sharing analytics
- custom domains
- distributed rate limiter
- production moderation operations dashboard

## Exit gate

- [ ] Only Approved version can publish.
- [ ] Public page is isolated, responsive, and functional.
- [ ] Public full-content non-persistence passes.
- [ ] Rate limits survive restart and protect Studio quota.
- [ ] Reset is secure/idempotent and preserves fixed sample.
- [ ] M1–M6 regressions pass.
- [ ] Evidence is recorded before moving to M8.
