# M9 — Task-first Studio and Chat-first Public Agent

## Status

In progress. The user approved this module on 2026-08-06 after reviewing the current
cloud UI and confirming that the product should emphasize use rather than repeatedly
promoting the Ocean Explorer sample.

## Problem

The accepted M8 interface is functional, but several application routes use landing-page
composition: oversized editorial headlines, repeated overview cards, and large sample-specific
copy appear before the primary task. Ocean Explorer is a useful seeded Agent, not the identity
of every Studio surface. The public route likewise makes visitors read an introduction before
they can use the Agent.

## Vertical outcome

Studio routes behave like a focused product workbench and the published route behaves like a
usable chat product. At a 1440 by 1000 desktop viewport, the primary action or primary working
content is visible without scrolling. At 375 px, the published conversation and composer take
priority over extended Agent metadata.

## Scope

### Shared Studio shell

- Retain the AgentSprout wordmark, three working destinations, role switch, session handling,
  and minimum 1024 px Studio boundary.
- Remove promotional sidebar copy and reduce decorative chrome that competes with tasks.
- Use compact page context instead of a landing-page hero.

### Access

- Make the access form the visual and reading-order priority.
- Keep the protected-Studio explanation, session-expiry state, privacy note, and all error states.
- Remove expedition/sample language that does not help a user enter the product.

### Workshop, Reviews, and Published

- Put the relevant Agent list or queue in the first viewport.
- Put `Create agent` in the Workshop page header for Student mode.
- Present the single available Knowledge Explorer template as a compact creation choice only
  when creation is requested; do not use Ocean Explorer as page branding.
- Replace repeated directory overview panels with compact, non-redundant status metadata.
- Keep Teacher/Student filtering, lifecycle semantics, links, and honest empty states unchanged.

### Agent Workspace

- Use a compact Agent context header showing name, version, lifecycle, and knowledge state.
- Place the four URL-backed stage tabs immediately after the context header.
- Preserve mounted panels, URL-fragment restoration, focus behavior, and locked-stage rules.
- Keep every field and action; only reorganize visual priority.

### Teacher Review

- Put version status, release gate/evaluation state, and the next Teacher action in a compact
  review header.
- Keep the evidence cases as the primary work surface once a run exists.
- Preserve the 16-case suite, progress, metrics, details, decisions, publication, withdrawal,
  reflection, comparison, and role behavior.

### Published Agent

- Use a compact header with Agent name, approval, version, and audience context.
- On desktop, place the conversation first and supporting Agent/source information in a
  secondary column. On mobile, conversation and composer precede extended metadata.
- Keep the composer visible in the first desktop viewport and reachable with a mobile keyboard.
- Change sample-specific input language to Agent-neutral language.
- Keep citations adjacent to answers and retain privacy, safety limitation, source attribution,
  loading, failure, timeout, and rate-limit states.
- The Agent's own name and content may be Ocean Explorer; the surrounding product shell may not
  imply that every Agent is Ocean Explorer.

## Acceptance criteria

1. At 1440 x 1000, Workshop shows the Agent list and create action; Reviews shows its queue;
   Published shows its releases; Workspace shows its stage navigation and selected panel;
   Teacher Review shows its evaluation action or evidence; Public shows the chat and composer.
2. No Studio route uses a display heading larger than the task content it introduces, and no
   overview panel repeats the same count/state already expressed by the list or empty state.
3. Ocean Explorer wording appears only where it is Agent data or a creation default, not as
   Studio navigation, generic form labels, generic loading language, or public composer wording.
4. The Published Agent at 375 px presents name/status, conversation, and composer before extended
   problem/goal/source details; no horizontal overflow occurs.
5. All existing API calls, persistence, role authorization, lifecycle transitions, runtime,
   evaluation, and publication behavior are unchanged.
6. Existing component tests, lint, typecheck, production build, browser flows, and axe checks pass.
7. New browser assertions verify first-viewport task visibility on desktop and chat-first order on
   mobile. Final desktop/mobile screenshots are reviewed without secrets or identifying data.

## Non-goals

- backend, schema, API, model, RAG, evaluation, session, or deployment changes
- new routes, templates, Agent types, settings, analytics, or administration
- a new design system or broad component rewrite
- removing the Ocean Explorer sample or changing its accepted content
- production support below 1024 px for Studio

## Verification

- repository documentation checker
- frontend lint, typecheck, component tests, and production build
- provider-boundary Playwright regression for Studio and Published Agent
- Chromium desktop screenshots at 1440 x 1000
- Chromium and WebKit public checks at 375 px
- axe scan with zero serious/critical violations and keyboard/focus smoke
- cloud smoke and CI after the accepted local commit is pushed

## Exit gate

- [ ] Documentation and acceptance boundaries are committed before implementation.
- [ ] Studio first-viewport task assertions pass.
- [ ] Published desktop and mobile chat-first assertions pass.
- [ ] Existing behavior and accessibility regressions pass.
- [ ] Screenshots are reviewed and evidence is recorded.
- [ ] Main is pushed, production is deployed, and final CI is green.
