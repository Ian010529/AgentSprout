# API Contracts

## 1. Conventions

- Base path: `/api/v1`
- Content type: JSON unless multipart upload is specified.
- IDs: opaque UUID strings.
- Times: UTC ISO-8601.
- Enums: uppercase snake case.
- All mutation endpoints accept `Idempotency-Key` where noted.
- Studio credentialed requests include the session cookie; Studio mutations also include `X-CSRF-Token`.
- Public endpoints never expose Studio entities or traces.

Success responses use the resource directly. Errors use:

```json
{
  "error": {
    "code": "STABLE_ERROR_CODE",
    "message": "Safe user-facing message",
    "request_id": "opaque-id",
    "retryable": false,
    "retry_after_seconds": null,
    "field_errors": {}
  }
}
```

Provider error bodies, stack traces, file system paths, and secrets are never returned.

## 2. Shared status codes

| Status | Meaning |
|---|---|
| `200` | successful read/update |
| `201` | resource created |
| `202` | background run accepted |
| `204` | successful no-content operation |
| `400` | malformed request or invalid CSRF |
| `401` | Studio session required/expired |
| `403` | role, lifecycle, or admin permission denied |
| `404` | resource not found or not visible |
| `409` | lifecycle conflict, duplicate active job, or idempotency conflict |
| `413` | upload too large |
| `415` | unsupported media type |
| `422` | field or document validation failure |
| `429` | rate limit exceeded |
| `500` | safe internal error |
| `503` | provider or readiness unavailable |
| `504` | operation timeout |

## 3. Health

### `GET /health`

Liveness only. Does not call OpenAI.

```json
{"status":"ok","service":"agentsprout-api"}
```

### `GET /ready`

Checks configuration presence, SQLite access, Chroma access, upload directory writeability, and migration version. It does not spend model tokens.

```json
{
  "status":"ready",
  "checks":{"sqlite":"ok","chroma":"ok","uploads":"ok","migrations":"ok"}
}
```

Returns `503` with safe failed-check names when not ready.

## 4. Studio access and session

### `POST /studio/access`

Body:

```json
{"access_code":"string"}
```

On success, sets an opaque Secure HttpOnly session cookie and returns:

```json
{
  "session":{"role":"STUDENT","expires_at":"..."},
  "csrf_token":"opaque-non-secret-token"
}
```

The access endpoint is rate limited. It never returns whether a partially matching code was supplied.

### `GET /studio/session`

Returns current role, expiry, and a refreshed CSRF token if the session is valid.

```json
{
  "session":{"role":"STUDENT","expires_at":"..."},
  "csrf_token":"rotated-opaque-token"
}
```

### `PATCH /studio/session/role`

Studio mutation. Body:

```json
{"role":"STUDENT"}
```

Allowed values: `STUDENT`, `TEACHER`.

### `DELETE /studio/session`

Revokes the server session and clears the cookie.

## 5. Agents and versions

### `GET /studio/agents`

Optional filters: `state`, `needs_review`. Returns summarized agent cards and server-authoritative next actions.

```json
{
  "agents":[
    {
      "id":"uuid",
      "display_name":"Ocean Explorer",
      "current_version":{"id":"uuid","number":1,"state":"DRAFT","knowledge_status":"NOT_ADDED"},
      "allowed_actions":["EDIT_DRAFT"],
      "next_action":"Continue defining the agent"
    }
  ]
}
```

### `POST /studio/agents`

Student-only. `Idempotency-Key` required.

```json
{
  "template":"KNOWLEDGE_EXPLORER",
  "project_name":"Ocean Explorer",
  "problem_to_solve":"...",
  "intended_users":"...",
  "audience_age":"AGE_12_17",
  "success_goal":"...",
  "welcome_message":"...",
  "tone":"CURIOUS",
  "response_length":"BALANCED",
  "custom_instructions":""
}
```

Returns `201` with `{ "agent": AgentAggregate, "version": VersionDetail }`. Reusing the same idempotency key and byte-equivalent logical request returns the same body and status. Reusing the key with different content returns `409 IDEMPOTENCY_CONFLICT`.

### `GET /studio/agents/{agent_id}`

Returns aggregate summary, all visible version summaries, current Draft, published version, and allowed actions for the current role.

The M2 aggregate is:

```json
{
  "id":"uuid",
  "display_name":"Ocean Explorer",
  "slug":"ocean-explorer-opaque",
  "current_draft_version_id":"uuid",
  "published_version_id":null,
  "versions":[{"id":"uuid","number":1,"state":"DRAFT"}],
  "allowed_actions":["EDIT_DRAFT"]
}
```

### `GET /studio/versions/{version_id}`

Returns full Studio configuration, knowledge status, reflection, lifecycle state, latest evaluation summary, reviews, and allowed actions.

From M3 onward, `knowledge_status` is one of `NOT_ADDED`, `PROCESSING`, `READY`, or `FAILED`, and the response includes:

```json
{
  "knowledge": {
    "active_document": {
      "id":"uuid",
      "original_filename":"ocean-literacy-2024.pdf",
      "status":"READY",
      "page_count":28,
      "chunk_count":42,
      "sha256":"lowercase-hex",
      "embedding_model":"text-embedding-3-small",
      "ready_at":"..."
    },
    "latest_job": null
  }
}
```

`active_document` remains the prior Ready document while a replacement is processing or fails. `latest_job` uses the ingestion-job response shape below and is present for the most recent staged upload.

### `PATCH /studio/versions/{version_id}`

Student-only, Draft-only. Partial editable fields from `docs/PRD.md`. Unknown or protected fields are rejected, not ignored.

M2 validation limits are: project name 3–80 characters; problem 10–500; intended users 3–240; success goal 10–300; welcome message 3–240; custom instructions 0–500. Strings are trimmed and control characters are rejected. At least one editable field is required.

### `POST /studio/versions/{version_id}/submit`

Student-only. `Idempotency-Key` required. Preconditions:

- state is Draft
- required configuration complete
- active document Ready
- no ingestion or chat job active

Returns the immutable `IN_REVIEW` version.

### `POST /studio/versions/{version_id}/next-version`

Student-only after `CHANGES_REQUESTED`, or from an Approved/Published version when creating an improvement.
`Idempotency-Key` is required. An unchanged Ready document is copied into isolated
version/document vector metadata without another embedding call and without consuming the
daily ingestion quota.

```json
{
  "what_changed":"Required description",
  "why_changed":"Required reason"
}
```

Copies configuration and document reference into a new Draft version. A later file replacement may stage a new document. Returns `201`.

## 6. Knowledge ingestion

### `POST /studio/versions/{version_id}/knowledge`

Student-only, Draft-only multipart upload. `Idempotency-Key` required. Field: `file`.

Synchronous checks occur before `202`:

- allowed extension and MIME
- maximum 15 MB
- safe filename
- daily ingestion quota
- no other workspace ingestion active
- SHA-256 duplicate recognition

Response:

```json
{
  "document_id":"uuid",
  "job_id":"uuid",
  "state":"UPLOADED",
  "duplicate":false
}
```

### `GET /studio/ingestion-jobs/{job_id}`

```json
{
  "id":"uuid",
  "document_id":"uuid",
  "state":"EMBEDDING",
  "progress":{"completed":3,"total":8},
  "safe_error":null,
  "retryable":false,
  "updated_at":"..."
}
```

### `POST /studio/ingestion-jobs/{job_id}/retry`

Student-only, failed job only, Draft-only. Creates a new job attempt for the same staged document without duplicating chunks. Returns `202` using the upload response shape with the new `job_id` and `duplicate:false`.

### `DELETE /studio/versions/{version_id}/knowledge/{document_id}`

Student-only, Draft-only. Cannot delete the active document of an immutable or published version. Removes staged/retired Draft resources using validated paths.

Stable ingestion error codes include:

- `FILE_TOO_LARGE`
- `UNSUPPORTED_FILE_TYPE`
- `PDF_ENCRYPTED`
- `PDF_SCANNED_OR_EMPTY`
- `PDF_PAGE_LIMIT`
- `PDF_PARSE_FAILED`
- `EMBEDDING_PROVIDER_FAILED`
- `INGESTION_TIMEOUT`
- `SERVICE_RESTARTED`
- `DUPLICATE_DOCUMENT`

## 7. Studio Playground runs

### `POST /studio/versions/{version_id}/runs`

Student or Teacher Studio session. `Idempotency-Key` required.

```json
{
  "message":"How do ocean currents affect climate?",
  "conversation_id":"optional-uuid"
}
```

The deterministic privacy guard runs before accepting/persisting raw content.

Response for both accepted normal and immediately blocked PII paths:

```json
{
  "run_id":"uuid",
  "conversation_id":"uuid",
  "phase":"QUEUED",
  "poll_after_ms":500
}
```

PII-blocked raw text is not included in any response echo or persistence.

### `GET /studio/runs/{run_id}`

While active:

```json
{
  "id":"uuid",
  "phase":"RETRIEVAL",
  "status":"RUNNING",
  "display_stage":"Searching the knowledge base…",
  "result":null,
  "safe_error":null
}
```

When complete:

```json
{
  "id":"uuid",
  "phase":"COMPLETED",
  "status":"COMPLETED",
  "result":{
    "type":"ANSWERED",
    "answer":"Validated text",
    "citations":[
      {
        "chunk_id":"opaque-id",
        "filename":"ocean-literacy.pdf",
        "page_number":12,
        "excerpt":"Supporting excerpt"
      }
    ]
  },
  "safe_error":null
}
```

Result types: `ANSWERED`, `BLOCKED`, `GUIDED`, `REFUSED`, `FAILED`.

### `GET /studio/conversations/{conversation_id}`

Returns allowed Studio messages, final results, and citations. It never returns blocked raw PII, raw unsafe output, hidden prompts, or full internal traces.

### `GET /studio/versions/{version_id}/conversation`

Returns the most recently updated, unexpired Studio conversation for refresh restoration, or
JSON `null` when no conversation exists. It uses the same allowlisted message shape as the
conversation-by-ID endpoint.

### `GET /studio/runs/{run_id}/trace`

Teacher-only. Returns sanitized ordered node traces, retrieval evidence, timings, model IDs, usage, and validation outcomes.

## 8. Evaluation

### `POST /studio/versions/{version_id}/evaluations`

Teacher-only. `Idempotency-Key` required. Preconditions:

- immutable submitted/changes-requested/approved/published version
- Ready document
- no active evaluation for this version
- daily evaluation quota available

Returns `202`:

```json
{
  "evaluation_run_id":"uuid",
  "state":"QUEUED",
  "total_cases":16,
  "completed_cases":0,
  "poll_after_ms":1000
}
```

### `GET /studio/evaluations/{evaluation_run_id}`

Returns persisted progress and, when complete, metrics and eligibility:

```json
{
  "id":"uuid",
  "version_id":"uuid",
  "state":"RUNNING",
  "progress":{"completed":7,"total":16,"passed":6,"failed":1,"errors":0},
  "models":{
    "online":"gpt-4o-mini-2024-07-18",
    "judge":"gpt-4.1-mini-2025-04-14",
    "embedding":"text-embedding-3-small",
    "moderation":"omni-moderation-latest"
  },
  "metrics":null,
  "release_eligible":false,
  "safe_error":null
}
```

### `GET /studio/versions/{version_id}/evaluations`

Teacher-only. Returns evaluation runs for the submitted version newest first, using the
same safe run-summary shape as the status endpoint. This restores active progress and lets
the Teacher select immutable historical runs after refresh.

### `GET /studio/evaluations/{evaluation_run_id}/cases`

Teacher-only. Returns case summaries and sanitized evidence. Filters: category, state, pass, blocking.

### `GET /studio/evaluation-cases/{case_result_id}`

Teacher-only. Returns expected behavior, displayed output, retrieved excerpts, deterministic checks, Judge scores/rationale, usage, timing, and trace link. PII case input is represented by a safe fixture label, not a real child's details.

### `GET /studio/versions/{left_version_id}/compare/{right_version_id}`

Teacher-only. Required query parameters: `left_run_id`, `right_run_id`. Server rejects comparison when suite version or pinned online/Judge/embedding models differ.

Returns server-derived comparison evidence:

```json
{
  "left":{"version_id":"uuid","version_number":1,"run_id":"uuid","release_eligible":false},
  "right":{"version_id":"uuid","version_number":2,"run_id":"uuid","release_eligible":true},
  "deltas":{
    "grounded_pass_rate":0.25,
    "age_average":0.5,
    "instruction_average":0.25,
    "latency_ms":-1200,
    "input_tokens":-300,
    "output_tokens":40,
    "estimated_cost_usd":-0.00012
  },
  "categories":[
    {"category":"KNOWLEDGE","left_passed":3,"left_total":4,"right_passed":4,"right_total":4,"passed_delta":1}
  ],
  "cases":[
    {"case_key":"KNW-01","category":"KNOWLEDGE","left_passed":false,"right_passed":true,"transition":"IMPROVED"}
  ]
}
```

Transition is `IMPROVED`, `REGRESSED`, or `UNCHANGED`. Deltas are right minus left.
The server sums persisted case latency and uses persisted run usage/cost; the client does
not recalculate evidence. Both runs must be completed, target their respective path
versions, contain the same enabled stable case keys, and share suite, online, Judge, and
embedding baselines. It does not collapse comparison into only one total score.

## 9. Teacher review and lifecycle

### `POST /studio/versions/{version_id}/request-changes`

Teacher-only, `IN_REVIEW` only.

```json
{"evaluation_run_id":"uuid","feedback":"Required actionable feedback"}
```

The referenced run must be completed and target this version. Returns the immutable
`CHANGES_REQUESTED` version plus the persisted review. It does not create or modify the
next Draft automatically.

### `POST /studio/versions/{version_id}/approve`

Teacher-only, `IN_REVIEW` only.

```json
{"evaluation_run_id":"uuid"}
```

The run must be completed, release eligible, use the required model baseline, and target this version. Returns `409 RELEASE_GATE_FAILED` otherwise.

### `POST /studio/versions/{version_id}/publish`

Teacher-only, `APPROVED` only. `Idempotency-Key` required.

```json
{"slug":"ocean-explorer"}
```

Atomically changes the agent's public version pointer. Returns the public URL path.

### `POST /studio/versions/{version_id}/withdraw`

Teacher-only, currently published version only. Removes public availability and marks the version Withdrawn. It does not delete evaluation evidence or knowledge.

## 10. Published Agent

### `GET /public/agents/{slug}`

Returns allowlisted published product data only:

- project name
- problem
- intended users
- success goal
- audience age
- welcome message
- version number
- approved/published labels
- knowledge-source attribution

No Studio IDs, instructions, traces, scores, or unpublished versions are returned.

### `POST /public/agents/{slug}/runs`

Public, rate limited. `Idempotency-Key` required.

```json
{"message":"What is ocean literacy?"}
```

Returns `202` with `run_id`, an opaque short-lived `run_token`, phase, and poll interval. The prompt is held in memory only after the privacy check and is not persisted.

### `GET /public/runs/{run_id}`

Requires `X-Public-Run-Token`. Returns only public display phase, final validated result/citations, or safe error. No trace, usage, model, score, or provider detail.

Public stable errors include:

- `PUBLIC_RATE_LIMITED`
- `GLOBAL_DEMO_LIMIT_REACHED`
- `PUBLIC_AGENT_UNAVAILABLE`
- `RUN_EXPIRED`
- `PROVIDER_TEMPORARILY_UNAVAILABLE`

## 11. Admin maintenance

### `POST /admin/reset-demo-workspace`

Not linked from UI. Requires `X-Admin-Reset-Token` and an `Idempotency-Key`.

Deletes temporary Studio agents, conversations, evaluation results, uploads, and vectors according to `docs/DATA_MODEL.md`, while preserving the fixed published sample. Returns only counts and a reset audit ID.

### `POST /admin/maintenance/cleanup`

Optional explicit maintenance trigger protected by the same admin secret. Normal cleanup also runs at startup and once per 24-hour request interval.

## 12. Validation limits

Initial field limits, also enforced server-side:

| Field | Limit |
|---|---:|
| project name | 80 characters |
| problem to solve | 500 characters |
| intended users | 300 characters |
| success goal | 500 characters |
| welcome message | 300 characters |
| custom instructions | 500 characters |
| change reflection fields | 500 characters each |
| teacher feedback | 1,000 characters |
| chat input | 1,000 characters |
| public slug | 3–60 lowercase letters, digits, hyphens |

HTML is treated as text and safely rendered. Unknown fields are rejected.

## 13. Idempotency

- Keys are scoped to session/public subject, endpoint, and target resource.
- Same key and same request returns the prior result.
- Same key with a different request returns `409 IDEMPOTENCY_KEY_REUSED`.
- Retain idempotency records long enough to cover browser retry windows; final duration is fixed in M1 and documented without changing behavior.
