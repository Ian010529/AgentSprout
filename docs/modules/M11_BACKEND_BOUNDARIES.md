# M11 — Backend Layer Boundaries

## Status

In progress on 2026-08-06. The user authorized backend layering and decoupling after reviewing
the M10 frontend boundary work.

## Problem

The backend has recognizable route, service, provider, persistence, and domain packages, but
several dependencies point against that intended layering. Service modules import HTTP-owned
`app.api.schemas` and `app.api.errors`; Evaluation and Publication import policy helpers from the
large Chat implementation; Review and Publication import a Chroma constant from Knowledge.
`chat.py` also combines command/runtime behavior with read-only response projections.

These dependencies do not currently form a cycle, but they make HTTP organization and individual
feature implementations upstream dependencies of business logic. The result is adequate for the
demo but unnecessarily broadens the impact of changes.

## Vertical outcome

Backend dependencies point inward: API routes adapt stable application contracts, services depend
on domain/application and infrastructure boundaries, and shared safety/rate-limit/vector concerns
have neutral owners. Chat commands and LangGraph execution remain behaviorally unchanged while
read-only Chat projections move to a dedicated query module.

## Dependency rule

```text
api/routes -> services -> domain/application contracts
                    \-> providers (protocols)
                    \-> db infrastructure

api compatibility exports -> domain/application contracts
```

- `services` must not import `app.api`.
- API compatibility modules may re-export application contracts and errors so existing route and
  exception-handler imports remain stable.
- Feature services may call another feature's explicit public operation, but must not import its
  private constants or unrelated policy helpers.
- No new dependency-injection, repository, unit-of-work, or client framework is introduced.

## Scope

- Move the shared `ApiError` ownership to the domain/application layer and retain an API re-export.
- Move Pydantic request/response contract ownership out of `app.api` and retain the existing
  `app.api.schemas` import surface for routes and tests.
- Update services to depend on the new contract and error owners.
- Extract deterministic Chat safety copy/detection into a pure safety-policy module.
- Extract shared Studio/global model window enforcement into a rate-limit module.
- Extract Chat read projections and phase presentation into a query module.
- Move the Chroma collection name to the DB/vector infrastructure layer.
- Add architecture/import-boundary tests that fail on a future `services -> api` dependency or
  invalid Chat boundary direction.

## Acceptance criteria

1. No module under `app/services` imports `app.api`.
2. Existing imports from `app.api.errors` and `app.api.schemas` remain valid and refer to the same
   application classes used by services.
3. Chat safety detection is pure and provider/persistence free; Chat queries do not own mutations;
   rate-limit helpers do not depend on Chat.
4. Evaluation and Publication no longer import safety or quota internals from `chat.py`; Review and
   Publication no longer import `COLLECTION_NAME` from Knowledge.
5. LangGraph nodes and edges, privacy-before-provider ordering, database commits, public retention,
   rate-limit scopes, API paths, payloads, errors, schemas, and lifecycle behavior are unchanged.
6. Ruff, Ruff format check, Pyright, all backend tests, empty migration, repository validation,
   frontend regression gates, and provider-boundary browser acceptance pass.
7. The internal backend import graph remains acyclic.

## Non-goals

- rewriting or renaming the LangGraph runtime
- introducing repositories, use-case classes, a unit-of-work, event bus, or dependency framework
- changing SQLAlchemy models, migrations, Chroma data, API contracts, errors, or frontend code
- merging every rate-limit implementation or extracting speculative interfaces
- splitting feature-cohesive Agent, Knowledge, Evaluation, Review, or Publication workflows

## Verification

- architecture import-boundary unit tests
- `ruff check app tests alembic`
- `ruff format --check app tests alembic`
- `pyright`
- `pytest`
- empty-database `alembic upgrade head`
- frontend lint, typecheck, tests, and production build
- provider-boundary browser lifecycle
- repository validation and GitHub CI

## Exit gate

- [x] Existing dependency direction and baseline tests are audited.
- [x] Scope, dependency rules, and behavior-preservation criteria are documented before code.
- [ ] Service-to-API reverse dependencies are removed with compatibility preserved.
- [ ] Chat policy, quota, queries, and vector infrastructure have explicit owners and no cycle.
- [ ] All local and cloud verification passes with evidence recorded.

