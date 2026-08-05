# M6 — Versions and Review

## Status

Pending M5 acceptance.

## Vertical outcome

The Teacher requests changes with feedback, the Student creates an immutable-comparable v2 with required reflection, both versions are evaluated on the same baseline, and only a release-eligible version can be approved.

## Frontend scope

- Teacher Request changes form with required feedback.
- Student feedback display and explicit `Create next version` action.
- v2 reflection fields: What changed and Why changed.
- Draft v2 copied configuration/knowledge state and editable controls.
- Version timeline and immutable state labels.
- Completed evaluation-run selectors for v1 and v2.
- Comparison view with category, case transition, latency, token, cost, and eligibility deltas.
- Approve action and clear release-gate explanation.
- All role/state-disabled actions explain why.

## Backend scope

- `IN_REVIEW → CHANGES_REQUESTED` with required feedback and referenced evaluation.
- Next Draft version snapshot creation and monotonic version numbering.
- Required v2+ reflections.
- Submitted/changes-requested/approved version immutability.
- Evaluation re-run for v2 through accepted M5 behavior.
- Comparison validation: same suite, online, Judge, embedding baseline.
- Case/category/performance delta calculation.
- `IN_REVIEW → APPROVED` only with a completed release-eligible run for the same version.
- Teacher review/audit persistence.
- Full server-side transition/role matrix.

## Data scope

- `teacher_reviews`
- version parent/reflection fields
- approval reference and timestamp
- no publication pointer yet

## API scope

- request changes
- create next version
- compare versions/runs
- approve
- existing Draft/update/upload/test/submit/evaluate routes reused, not duplicated

## Transition rules

- Request changes never unlocks the submitted version.
- Next version copies configuration and may reference/copy the Ready document without re-embedding unchanged content, provided retrieval remains version-isolated through safe metadata/linkage. The exact implementation must preserve immutable evidence and is verified before reuse.
- Replacing knowledge in v2 creates v2-specific ingestion/chunks.
- Approval never auto-publishes.
- No client can pass an arbitrary `release_eligible=true` value.

## Automated checks

- complete legal/illegal transition matrix by role
- feedback and reflection validation
- concurrent next-version/idempotency/version-number behavior
- immutable direct update/upload attempts
- safe unchanged-document reuse versus replaced-document isolation
- compare accepts matching and rejects mismatched baselines
- approval rejects missing/wrong/failing/error evaluation run
- frontend version timeline, forms, comparison, error/accessibility states
- Playwright Student submit → Teacher request changes → Student v2 → evaluate → compare → approve

## Manual verification

1. Request changes on v1 with and without feedback.
2. Attempt to edit v1 directly.
3. Create v2 and confirm both reflection fields.
4. Change one bounded configuration and submit/evaluate.
5. Compare matching completed runs.
6. Attempt mismatched-run comparison.
7. Attempt approval with failing/wrong run, then approve eligible v2.
8. Verify v1 evidence remains unchanged.

## Acceptance mapping

- `ACC-VER-001`
- `ACC-VER-002`
- approval/request-change portions of `ACC-REV-001`

## Non-goals

- public publication
- arbitrary many-version analytics beyond available timeline and selected pair
- collaborative comments or notifications
- editable evaluation results

## Exit gate

- [ ] Immutability and new-version behavior pass through UI and direct API.
- [ ] Reflection and Teacher feedback are required where contracted.
- [ ] Same-baseline comparison is correct and rejects invalid pairs.
- [ ] Approval is server-gated by eligible evaluation.
- [ ] M1–M5 regressions pass.
- [ ] Evidence is recorded before moving to M7.

