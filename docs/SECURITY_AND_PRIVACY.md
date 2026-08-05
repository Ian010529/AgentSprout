# Security and Privacy

## 1. Scope and disclaimer

AgentSprout Studio is an interview MVP for supervised demonstration. It is not approved for unsupervised child use, school production deployment, or emergency/safeguarding response. A real launch would require legal review, guardian/school consent flows, data-processing agreements, incident procedures, and region-specific child-privacy compliance.

The MVP still applies privacy-by-design and safe-default principles so that the demo architecture does not normalize unsafe handling.

## 2. Protected assets

- OpenAI API key
- Studio access code
- session signing secret
- admin reset token
- normal Studio conversation content
- uploaded knowledge documents
- unpublished configurations and versions
- teacher feedback and evaluation evidence
- run traces and provider usage
- public cost quota

## 3. Trust boundaries

```text
Untrusted browser
  → Vercel frontend
  → public Railway HTTPS API
  → authenticated Studio/public/admin boundary
  → application services
  → persistent volume and OpenAI
```

All browser input, filenames, cookie state, role claims, forwarded IP headers, model output, PDF content, and provider errors are untrusted.

## 4. Threats and controls

| Threat | Required control |
|---|---|
| OpenAI key theft | backend-only secret; no browser bundle, response, log, or Git exposure |
| access-code brute force | rate limit, constant-time comparison, generic failure, no code logging |
| CSRF on Studio mutation | CSRF token plus Secure HttpOnly cookie and exact Origin/CORS allowlist |
| client role manipulation | server-session role; backend authorization on every protected action |
| public API cost abuse | per-IP limits, global quota, input/output caps, evaluation and ingestion quotas |
| PII sent to model | deterministic pre-provider guard; canary test verifies provider not called |
| PII persisted | create only sanitized blocked run/event; never store or echo blocked raw text |
| prompt injection | explicit classifier/route, fixed system rules, retrieved-context delimiting, no secret in prompt |
| unsafe output streamed | buffer complete output; moderation and citation validation before display |
| model hallucination | evidence threshold, context-only instruction, citation IDs, validation, eval gate |
| malicious upload | allowlist, size/page limits, sanitized filename, isolated parser path, no execution |
| path traversal | generated storage IDs; resolved path must remain under configured data root |
| public trace disclosure | separate public DTOs and endpoints; no internal IDs/config/usage |
| SQLite/Chroma corruption | single backend replica, WAL, staged vector writes, persistent volume, smoke checks |
| stale job shown as successful | persisted heartbeat/state; restart converts unfinished jobs to failed |
| secret in Git | `.gitignore`, CI secret scan, `.env.example` with placeholders only |
| XSS from chat/document | React text rendering; no unsafe HTML; CSP and security headers |

## 5. PII policy

### MVP blocked categories

- email address
- telephone number
- detailed street/home address
- obvious requests to collect or reveal those values

The detector may use deterministic patterns and bounded context rules. It must run before raw Studio-message persistence, public job persistence, embedding, Moderation, or generation.

### Blocked-event data

Allowed to store:

- event category, such as `PII_EMAIL`
- action `BLOCKED_BEFORE_PROVIDER`
- run/version identifiers
- detector version
- timestamp and timing

Forbidden to store:

- matched text
- surrounding raw prompt
- reconstructed or partially masked contact details
- a reversible hash of the PII

The response does not repeat the sensitive value. It gives a general privacy reminder and recommends speaking with a trusted adult when appropriate.

## 6. Child-facing content policy

- Audience age is mandatory and server-authoritative per version.
- Responses must follow the word, vocabulary, and homework limits in `docs/PRD.md`.
- Moderation runs on allowed input and complete output.
- Sexual, graphic violent, hateful, self-harm, and other unsafe categories receive short, non-graphic responses.
- Immediate danger/self-harm responses recommend contacting a trusted adult or local emergency service. The MVP does not geolocate, notify a school, or claim live intervention.
- The agent never claims to be a human teacher, counselor, doctor, or emergency professional.

## 7. Homework policy

Disallowed behavior is producing a polished, submission-ready answer when the user asks the agent to do assessed work for them.

Allowed behavior:

- explain a relevant concept from the knowledge source
- give bounded hints or an approach
- ask a guiding question
- provide a checklist
- comment on a student's supplied attempt

The specific response depth depends on the configured age mode.

## 8. Prompt-injection policy

- Treat uploaded content and user text as data, not authority.
- Keep safety and lifecycle rules in system/developer instructions outside retrieved text.
- Do not include API keys, access codes, reset tokens, database paths, or private configuration in any model prompt.
- Refuse requests to reveal hidden instructions or ignore safety/knowledge rules.
- Do not return raw retrieval stores, other versions, other conversations, or teacher-only data.
- Evaluation includes direct, indirect, and knowledge-boundary injection cases within the fixed scope.

## 9. Data minimization and retention

### Studio

- Allowed normal Student messages, final validated answers, citations, and sanitized traces are stored for teacher review.
- Studio conversations expire after 30 days.
- Deleting/resetting an Agent cascades its eligible conversations, traces, uploads, and vectors.

### Published Agent

- Full anonymous prompts and answers are not persisted.
- The process may hold them in memory only while the run/result token is active.
- Store only rate-limit buckets, token/latency totals, result category, and sanitized safety events.

### Evaluation

- Fixed synthetic cases do not use real child details.
- Results remain while the Agent exists to support version comparison.

### IP handling

- Normalize only from trusted proxy information.
- Store a keyed hash scoped for rate limiting, not a raw IP.
- Rotate the key only with an explicit plan because rotation resets buckets.

## 10. Session and authorization

- Shared Studio access code creates a short-lived opaque server session.
- Store only a token hash server-side.
- Cookie flags in production: `Secure`, `HttpOnly`, and the cross-site SameSite value required by the Vercel/Railway topology.
- Every Studio mutation also requires a CSRF token bound to the session.
- Session expiry and revocation are enforced server-side.
- Student and Teacher permissions follow the state machine; hidden buttons are not authorization.
- Admin reset uses a separate secret and endpoint, never the Studio access code.

This gate is not multi-user authentication. The UI and README must not describe it as such.

## 11. File security

- Ignore the client filename for directory construction.
- Use generated IDs and a validated allowlisted extension.
- Resolve and verify every delete target is a descendant of `DATA_DIR/uploads`.
- Reject symlinks, encrypted PDFs, parse failures, page-limit violations, empty/scanned content, and unsupported media.
- Do not execute macros, scripts, embedded files, or active PDF content.
- Serve no original upload directly to public visitors in the MVP.
- The NOAA demo source must remain unchanged and be accompanied by source/license/checksum metadata.

## 12. Provider data handling

- Send only the minimum allowed prompt, required system policy, and retrieved excerpts.
- PII-blocked input never reaches OpenAI.
- No child name, school, birthday, guardian contact, or profile is collected.
- Use privacy-preserving stable safety identifiers if required by the configured OpenAI API guidance; do not use raw user identifiers.
- Provider request IDs may be stored for support without storing blocked content.
- Document that OpenAI/provider retention and production data controls require review before real child deployment.

## 13. Logging and traces

Structured logs may include:

- request/run ID
- endpoint and status
- stable error code
- sanitized actor type
- timing, retry, and provider request ID

Logs and traces must exclude:

- authorization/cookie headers
- secrets
- raw access or reset values
- raw blocked PII
- raw unsafe output
- system prompts
- full public chat content
- file-system paths visible outside the server

Teacher traces use an allowlist, not a denylist.

## 14. Security headers and transport

- HTTPS only in production.
- Exact CORS origins; no wildcard with credentials.
- Content Security Policy suitable for the deployed frontend.
- `X-Content-Type-Options: nosniff`.
- clickjacking protection through `frame-ancestors`.
- restrictive Referrer Policy.
- API responses containing Studio data use no-store caching.
- Public static product metadata may use bounded cache controls; run results may not.

## 15. Incident behavior

- Provider outage: return stable retryable error; do not generate local fallback text.
- suspected secret exposure: rotate secret, revoke sessions, inspect sanitized audit records, and redeploy.
- corrupted vector/document state: make version unavailable for new runs, retain evidence, and require re-ingestion.
- persistent safety failure: block approval/publication and retain the failing evaluation evidence.
- no automatic external notifications are sent in the MVP.

## 16. Production gaps

Before deployment to real children, obtain expert review for consent, age assurance, parental controls, school administration, data residency, DPA terms, safeguarding escalation, audit retention, abuse reporting, account recovery, staff permissions, deletion requests, and jurisdiction-specific privacy obligations.

