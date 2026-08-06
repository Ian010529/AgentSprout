# M5 — Teacher Evaluation

## Status

Accepted on 2026-08-06. Reproducible evidence is recorded in
[`docs/evidence/M5_ACCEPTANCE.md`](../evidence/M5_ACCEPTANCE.md).

## Vertical outcome

The Student submits an immutable v1, the Teacher starts a real 16-case evaluation, progress survives refresh, every result contains reproducible evidence, and the server computes release eligibility without editable or hard-coded scores.

## Frontend scope

- Workspace Submit section for first-version readiness and submission.
- Read-only submitted-version display.
- Teacher Review route with version summary and reflection display.
- Run evaluation action with duplicate/active-run prevention.
- Real queued/running/completed/failed status and `completed / 16`.
- Metric cards, release-gate result, model baseline, usage, latency, and cost.
- Filterable case table and failure detail.
- Sanitized trace/evidence linkage per case.
- Refresh/restoration and historical run selection.
- Clear infrastructure-error and release-blocked presentation.

## Backend scope

- Draft readiness validation and `DRAFT → IN_REVIEW` submission.
- Exactly 16 idempotently seeded case definitions and suite version.
- Exact NOAA knowledge/out-of-knowledge case content authored only after source inspection.
- Asynchronous evaluation job with maximum concurrency three.
- Real invocation of the accepted M4 runtime for every case.
- Immediate persistence of each completed case result and progress counters.
- Deterministic route, generation-call, citation, PII canary, and schema checks.
- Pinned Judge structured rubric for evidence support, age appropriateness, and instruction following.
- Release-threshold calculation.
- One active evaluation per version, daily quota, timeout/restart behavior.
- Completed evaluation immutability.

## Data scope

- `evaluation_cases`
- `evaluation_runs`
- `evaluation_case_results`
- suite/rubric version metadata
- submission timestamp/state

## API scope

- version submit
- evaluation create/status/case list/case detail
- no Request changes, new version, approve, compare, or publish yet

## Evaluation suite authoring requirements

- Distribution is exactly 4 knowledge, 3 out-of-knowledge, 3 privacy, 2 homework, 2 injection, 2 age.
- Knowledge cases identify expected NOAA pages/evidence after extraction.
- Out-of-knowledge cases are reviewed against the document.
- PII values are synthetic canaries.
- Expected behavior and deterministic checks are explicit.
- Judge rubric is versioned and requires short evidence-based rationale.
- Case wording changes create a new suite version when they affect behavior/comparability.

## Automated checks

- seed idempotency and exact category counts
- concurrency maximum three
- progress persistence and refresh
- active-run conflict and evaluation quotas
- individual provider error/retry and overall timeout
- restart handling
- deterministic threshold matrix
- Judge structured response/malformed response handling
- completed-run immutability
- no score-edit API
- frontend progress, filters, error, evidence, and accessibility states
- Playwright submit → Teacher run → progress → completed/failure detail
- opt-in real 16-case run for final M5 acceptance

## Manual verification

1. Confirm version cannot submit without Ready knowledge.
2. Submit v1 and confirm editing is locked.
3. Start evaluation and observe real progress.
4. Refresh during execution and restore progress.
5. Inspect at least one pass, one blocking failure fixture/run, and one infrastructure error behavior.
6. Verify model IDs, token use, cost, trace, and citation evidence.
7. Attempt a second active run and score mutation.
8. Complete one live real suite and retain sanitized report.

## Acceptance mapping

- `ACC-EVL-001`
- `ACC-EVL-002`
- `ACC-EVL-003`
- submission part of `ACC-VER-001`

## Non-goals

- request changes or approval
- v2 creation/comparison
- publication/public chat
- manual case or score editing
- background queue infrastructure

## Exit gate

- [x] Exact 16-case suite and evidence map are reviewed.
- [x] Async progress and refresh behavior pass.
- [x] Real suite results are not hard-coded.
- [x] Thresholds and infrastructure-error blocking pass.
- [x] Submitted version is immutable.
- [x] M1–M4 regressions pass.
- [x] Live report records models/time/usage/cost.
- [x] Evidence is recorded before moving to M6.
