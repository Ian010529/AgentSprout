# M0 — Documentation and Contracts

## Status

Complete and approved by the user on 2026-08-06.

## Outcome

Create one coherent, implementation-ready specification for the product, UX, architecture, data, APIs, safety/privacy, testing, acceptance, deployment, demo, decisions, and every later vertical module.

## Authorized changes

- Markdown documentation under the project root and `docs/`.
- Documentation directory creation.
- Read-only inspection needed to verify paths and consistency.

## Forbidden changes

- application source code
- package/dependency manifests or lockfiles
- `.venv`, `node_modules`, generated project scaffold
- `.env` or real secrets
- database, Chroma, upload, or runtime directories
- downloaded NOAA PDF
- Docker/Vercel/Railway configuration
- Git initialization, commit, push, or cloud-resource creation

## Required documents

- `AGENTS.md`
- `README.md`
- `docs/CURRENT_MODULE.md`
- `docs/PRD.md`
- `docs/UX_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_MODEL.md`
- `docs/API_CONTRACTS.md`
- `docs/SECURITY_AND_PRIVACY.md`
- `docs/TEST_STRATEGY.md`
- `docs/ACCEPTANCE_TESTS.md`
- `docs/DEPLOYMENT.md`
- `docs/KNOWLEDGE_SOURCE.md`
- `docs/DEMO_RUNBOOK.md`
- `docs/DECISION_LOG.md`
- `docs/modules/README.md`
- module documents M0 through M8

## Contract review checklist

- Product scope and explicit non-goals agree across documents.
- Routes and UI states map to actual API endpoints and enums.
- State machine agrees across PRD, data model, API, and M6.
- Storage and cloud topology agree across architecture, data, deployment, and M8.
- Models and evaluation thresholds are consistent.
- Safety order guarantees PII before provider/persistence.
- Public retention differs correctly from Studio retention.
- Long-running ingestion, chat, and evaluation have persisted status behavior.
- Every acceptance scenario belongs to a specific module.
- No document claims unimplemented commands have been verified.
- All real paths point to `/Users/chl/Desktop/my_project/AgentSprout`.

## Verification

Run documentation-only checks:

```text
find project files and confirm only documentation exists
search for conflicting model IDs, storage choices, state enums, and limits
search for accidental secret-like values
inspect all Markdown links and module references
```

## Exit evidence

- Complete file list: 25 Markdown files, including all M0–M8 module documents.
- Local Markdown link check: passed on 2026-08-06.
- Documentation-only file check: passed; no non-Markdown files exist.
- Wrong-workspace/secret-like assignment scan: passed.
- No business code, dependency manifest, virtual environment, runtime data, deployment configuration, or downloaded asset was created.
- User review and approval in the conversation.

## Exit gate

- [x] Every required document exists and is internally complete.
- [x] Cross-document consistency review passes.
- [x] Target directory is confirmed.
- [x] No forbidden implementation artifact exists.
- [x] User explicitly approves the documentation set.
- [x] `docs/CURRENT_MODULE.md` is updated to M1 only after approval.
