# M10 API Client Boundaries Acceptance Evidence

Acceptance ID: `ACC-MOD-001`, regression of `ACC-CI-001`, `ACC-PUB-001`,
`ACC-PUB-003`, and `ACC-PUB-004`

Documentation commit: `7b6dddf`

Implementation commit: `8a4e016`

Environment: macOS, Node.js 24 runtime, Next.js 16.3.0, isolated FastAPI
provider-boundary server, empty migrated SQLite/Chroma data directory, Chromium and WebKit

Commands and results:

- `pnpm lint` — passed
- `pnpm typecheck` — passed; all existing `@/lib/api` consumers compile unchanged
- `pnpm test` and `NEXT_PUBLIC_API_BASE_URL=/api-proxy pnpm test` — 9 files and 34 tests
  passed with both the local direct base URL and production same-origin proxy
- `pnpm build` — production build passed; all eight routes generated
- `python3 scripts/check_repository.py` — passed
- `node backend/tests/run_m7_browser.cjs` against the isolated production frontend and
  provider-boundary backend — passed
- `git diff --check` — passed

Boundary evidence:

- `frontend/src/lib/api.ts` is a five-line compatibility entry point.
- Contract types, transport/error normalization, system endpoints, Studio endpoints, and public
  endpoints have separate owners.
- Endpoint modules import only the transport and type modules. The transport and type modules do
  not import endpoint modules, so the internal dependency graph is acyclic.
- New unit assertions preserve Studio credentials, CSRF, and idempotency headers and preserve
  credential-free public polling with the opaque run token.
- Existing components and routes required no import changes.

Browser result:

```json
{"published":true,"chromium_citation":true,"webkit_375":true,"axe_violations":0,"reduced_motion":true,"direct_mutation_denied":true,"rate_limit_state":true,"console_errors":0}
```

No backend, route, component, stylesheet, API contract, persistence, model, deployment, or
user-visible behavior changed.

Accepted on 2026-08-06.
