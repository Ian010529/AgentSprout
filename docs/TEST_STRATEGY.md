# Test Strategy

## 1. Principles

- Test each vertical module at its public contract boundary.
- Keep normal CI deterministic and free of provider cost.
- Keep runtime honest: no fake model, offline response, hard-coded score, or simulated job progress.
- Require explicit live tests before accepting modules that integrate OpenAI.
- Every fixed bug receives the smallest regression test that would have caught it.

## 2. Test layers

### Backend unit tests

Cover pure application behavior:

- PII detectors and redaction-free event creation
- lifecycle transition matrix
- validation limits and protected fields
- age-mode prompt policy construction
- chunk boundary and page attribution logic
- citation ID validation
- rate-limit window arithmetic
- retention and safe path resolution
- evaluation threshold calculation
- cost estimation from recorded usage

External provider calls are replaced only at the adapter/HTTP boundary. Tests assert call/no-call behavior and our response handling; they do not claim to test model quality.

### Backend integration tests

Use temporary SQLite, temporary Chroma persistence, and temporary upload roots. Cover:

- migration from empty database
- repository transactions and constraints
- staged knowledge replacement and rollback
- idempotency behavior
- restart recovery for unfinished jobs
- deletion across SQLite/Chroma/files
- API authentication, CSRF, role, lifecycle, and public DTO isolation
- deterministic evaluation checks

### Frontend unit/component tests

Cover:

- form validation and server field errors
- every required component state
- role-specific actions
- job progress mapping from server enums
- citation rendering
- release-gate and comparison presentation
- accessibility labels, focus, live regions, and reduced motion
- safe error rendering without provider detail

### Browser E2E

Playwright runs vertical flows against the real local frontend/backend with provider-boundary test responses:

- Studio access and expiry
- create and refresh Agent
- upload success/failure/retry
- normal chat and citation display
- five safety routes
- submit/evaluate/request changes/new version/approve/publish
- public chat and public mutation denial
- rate-limit UI
- reset preservation of fixed public sample

Chromium covers all core flows. Published Agent critical chat/citation flow also covers WebKit and a 375 px viewport.

### Live provider tests

Marked and skipped unless `RUN_LIVE_TESTS=1` and required secrets exist. Cover:

- one embedding request and expected dimension/non-empty result
- one grounded online answer with structured output
- one Judge structured rubric result
- one Moderation request
- NOAA retrieval smoke test
- final 16-case acceptance evaluation

Each live report records timestamp, exact model IDs, latency, usage, result, and estimated cost. A live failure is not replaced with a test fixture.

## 3. No-mock boundary

Allowed in ordinary tests:

- intercepting the official OpenAI adapter's outbound request
- returning a schema-valid provider response fixture
- simulating `429`, timeout, `5xx`, malformed structured output, or moderation outcome
- verifying retry and failure behavior

Forbidden in application runtime:

- a fake/offline model mode
- canned Ocean Explorer answers
- a "demo success" switch
- hard-coded evaluation scores
- client-side fake ingestion/evaluation progress
- automatic fallback to another model

## 4. PII canary testing

Privacy acceptance requires more than checking the displayed block message:

1. Send synthetic phone, email, and address fixtures.
2. Assert the provider adapter recorded zero calls for the run.
3. Search allowed SQLite content fields for unique canary fragments.
4. Search Chroma documents/metadata for the same fragments.
5. Search captured structured logs.
6. Confirm only the safe category event exists.

Never use real personal details in fixtures.

## 5. Ingestion testing

Fixtures include:

- valid TXT
- valid Markdown
- small text PDF with known page text
- unchanged NOAA CC0 PDF for live acceptance
- encrypted PDF
- scanned/image-only PDF
- empty file
- unsupported extension/MIME mismatch
- over-size metadata/path test without committing a large binary
- duplicate file
- parser failure
- embedding timeout and partial batch failure

Assertions cover page attribution, stable chunk IDs, no duplicates after retry, and preservation of the previous active document.

## 6. Evaluation testing

- Seed exactly 16 enabled cases for the suite version.
- Assert category counts: 4/3/3/2/2/2.
- Assert three-case concurrency limit.
- Persist each completed result before the job completes.
- Refresh/poll returns accurate counters.
- A case infrastructure error prevents release eligibility.
- Any blocking safety failure prevents release eligibility.
- Compare rejects mismatched suite or model baselines.
- Completed runs are immutable.

The exact NOAA knowledge questions are reviewed against the downloaded document and recorded with evidence references during M5.

## 7. CI checks

Planned GitHub Actions checks:

### Backend

- Ruff lint and format check
- Pyright type check
- Pytest unit/integration suite
- Alembic upgrade from empty database

### Frontend

- ESLint
- TypeScript type check
- Vitest
- Next.js production build

### System

- Playwright core E2E
- backend Docker image build
- secret/runtime-data scan
- documentation-link and contract consistency checks where practical

Live tests are a separate manual workflow. They do not run on every push.

## 8. Module test rule

Before leaving a module:

1. run that module's commands
2. run all prior regression suites
3. record evidence in the module document or linked artifact
4. verify no critical-path skip/TODO remains
5. verify browser console is clean for the module flow

No module may rely on "final integration" to establish its basic frontend/backend contract.

## 9. Test data rules

- Use synthetic identities and contact canaries only.
- Do not commit real child conversations or identifying screenshots.
- Provider fixtures contain invented, non-sensitive content.
- Test databases, Chroma directories, uploads, traces, videos, and screenshots are isolated from production data.
- Acceptance screenshots are reviewed for secrets and PII before committing.

## 10. Performance targets

Measured under a warmed, healthy demo environment:

| Operation | Target | Hard failure/timeout |
|---|---:|---:|
| normal chat | under 8 seconds | provider request 20 seconds; run governed by safe failure |
| NOAA ingestion | under 90 seconds | 3 minutes |
| 16-case evaluation | under 2 minutes | 5 minutes |
| ordinary API reads | p95 under 500 ms locally/cloud target | documented if platform cold start dominates |

Targets are reported, not achieved through fake delays or cached canned answers.
