# AgentSprout Studio — Development Rules

This file governs every change under `/Users/chl/Desktop/my_project/AgentSprout`.

## Mandatory resume protocol

After any context compaction, task resume, handoff, or interruption, do not edit files immediately. Read these files in order:

1. `AGENTS.md`
2. `docs/CURRENT_MODULE.md`
3. The module document linked from `docs/CURRENT_MODULE.md`
4. `docs/DECISION_LOG.md`
5. Any contract document explicitly referenced by the current module

Then inspect the current diff and test status. Continue from the recorded module state; do not restart the project or infer a new architecture from memory.

## Module gate

- Work on exactly one module at a time.
- Do not edit later-module implementation files in advance.
- A module is complete only when every acceptance item in its module document has evidence and all prior regression tests pass.
- If a module fails, stay in that module and fix it. Do not defer a known defect to final integration.
- Update `docs/CURRENT_MODULE.md` only after the current module is accepted.
- M0 is documentation-only. No application source code, dependency manifest, virtual environment, generated UI, database, or deployment may be created until the user approves M0.

## Change discipline

- Search for an existing function, component, type, schema, fixture, or helper before adding one.
- Reuse existing code and data structures whenever they satisfy the current requirement.
- Make the smallest change that meets the current module contract.
- Do not refactor unless the current feature cannot be implemented safely without it.
- Do not perform opportunistic cleanup, broad renames, directory reshuffles, dependency migrations, or unrelated formatting.
- Do not change a public API, database schema, event name, or state transition without updating the relevant contract and decision log first.
- Preserve user-authored changes and unrelated work.
- Do not hide failures with fallback answers, fake progress, hard-coded scores, or skipped tests.

## Frontend and backend must ship together

Modules M2–M7 are vertical slices. Each must complete its frontend states, backend behavior, API contract, persistence, and browser acceptance flow before moving on.

Every networked UI must handle:

- loading
- empty
- success
- validation error
- authorization error
- server error
- timeout
- rate limit
- disabled/submitting
- retry where safe
- state restoration after refresh where required

The UI must never display simulated processing progress. Displayed stages and counters must come from persisted backend state.

## Model and safety rules

- Runtime and live acceptance use real OpenAI APIs. The product must not contain a fake model or offline answer fallback.
- Unit and CI tests may replace external HTTP responses only at the provider boundary, as defined in `docs/TEST_STRATEGY.md`.
- Never send PII-blocked input to OpenAI or persist the blocked raw text.
- Never expose unvalidated streamed model tokens to a child-facing UI.
- Never log API keys, access codes, reset tokens, raw session tokens, or unredacted PII.
- Model IDs are configuration, but comparison runs must record and use the same pinned snapshots.

## Secrets and data

- Real secrets belong only in local `.env`, Railway secrets, or explicitly configured GitHub secrets.
- Never commit `.env`, SQLite databases, Chroma data, uploaded files, logs, or generated traces.
- Browser code may receive only the non-secret public API base URL.
- Public chat content is not persisted. Studio content follows the retention policy in `docs/SECURITY_AND_PRIVACY.md`.

## Verification

- Run the current module's documented checks before claiming completion.
- Run all existing regression checks after each module.
- Do not mark an acceptance item complete without a command result, API result, screenshot, or other reproducible evidence.
- Keep browser console output free of application errors in accepted flows.
- Live tests must be opt-in and must report model IDs, token use, latency, and timestamp.

## Documentation ownership

- `docs/PRD.md` owns product scope.
- `docs/UX_SPEC.md` owns routes, copy, UI states, and responsive behavior.
- `docs/ARCHITECTURE.md` owns component boundaries and runtime flows.
- `docs/DATA_MODEL.md` owns persistent entities and deletion behavior.
- `docs/API_CONTRACTS.md` owns endpoint and error contracts.
- `docs/SECURITY_AND_PRIVACY.md` owns threat controls and retention.
- `docs/ACCEPTANCE_TESTS.md` owns end-to-end release criteria.
- `docs/DECISION_LOG.md` records approved decisions and later changes.
- `docs/modules/*.md` own module scope and exit gates.

If documents disagree, stop implementation, resolve the conflict in M0-style documentation, and record the resolution in `docs/DECISION_LOG.md`.

