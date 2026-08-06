# M10 — Frontend API Client Boundaries

## Status

In progress on 2026-08-06. This module follows a dependency audit requested by the user.

## Problem

The repository has sound system-level boundaries: frontend routes delegate to feature components,
the backend separates routes, services, providers, persistence, and domain enums, and provider
protocols isolate OpenAI adapters. The main actionable coupling hotspot is
`frontend/src/lib/api.ts`. It currently owns all API contract types, HTTP transport and safe-error
normalization, and the system, Studio, and public endpoint groups in one file. A contract edit,
transport edit, or endpoint edit therefore shares one change surface even though those concerns
have different reasons to change.

Large backend feature services and the global stylesheet were reviewed but are outside this
module. `chat.py` coordinates safety-critical runtime, idempotency, rate limits, and persistence;
splitting it without a dedicated behavioral objective would increase transaction and regression
risk. `globals.css` is order-sensitive visual debt, not an API dependency boundary, and moving its
rules would create cascade risk without improving runtime decoupling.

## Vertical outcome

The frontend retains one stable `@/lib/api` public entry point while its contract types, shared
transport, and three endpoint groups have explicit internal ownership. Existing components and
tests require no import migration, and browser-visible behavior is unchanged.

## Scope

- Move API contract types into a type-only module.
- Move base URL handling, fetch wrappers, CSRF behavior, timeout behavior, and `ApiError` into a
  shared transport module.
- Move system, Studio, and public endpoint groups into separate modules.
- Keep `frontend/src/lib/api.ts` as a compatibility barrel with the same named exports.
- Add focused tests for the public entry point and shared request behavior where current coverage
  is insufficient.
- Record the concrete boundary in the architecture documentation.

## Acceptance criteria

1. Every existing named import from `@/lib/api` remains valid with the same TypeScript shape.
2. Endpoint methods, paths, HTTP verbs, payloads, credentials, CSRF headers, timeouts, polling, and
   safe-error normalization remain unchanged.
3. Contract types, transport logic, system endpoints, Studio endpoints, and public endpoints live
   in separately owned modules with an acyclic internal import graph.
4. No backend, component, route, stylesheet, schema, model, deployment, or dependency changes are
   introduced.
5. API unit tests, all frontend component tests, lint, typecheck, and production build pass.
6. The existing provider-boundary browser regression and repository documentation checker pass.

## Non-goals

- redesigning the frontend API surface or renaming consumer imports
- splitting backend feature services or changing transaction boundaries
- reorganizing CSS, components, routes, or page state
- adding a data-fetching framework, generated client, state manager, or dependency
- changing any user-visible behavior

## Verification

- repository documentation checker
- frontend lint, typecheck, component tests, and production build
- import-cycle check for the new API modules
- provider-boundary Playwright regression
- git diff review confirming the compatibility entry point and scope boundary

## Exit gate

- [x] Audit identifies a concrete coupling problem and records excluded hotspots with reasons.
- [x] Module boundary and acceptance criteria are documented before implementation.
- [ ] API client modules have single, explicit ownership and an acyclic dependency direction.
- [ ] Existing public imports and runtime behavior are preserved by tests.
- [ ] All scoped verification passes and evidence is recorded.

