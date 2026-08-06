# UX and Frontend Specification

## 1. Brand

- Product name: **AgentSprout Studio**
- Tagline: **Students build. Teachers evaluate. Safe agents get published.**
- Independent concept brand; do not use Bytewise names, logos, screenshots, or imply affiliation.
- Tone: constructive, calm, direct, and age-aware. Avoid gamified pressure and generic AI hype.

## 2. Visual direction

- Deep-ocean navy for the application frame.
- Off-white reading surfaces for forms, conversations, and evidence.
- Blue-green for growth, approval, and published states.
- Coral orange for warnings and high-attention actions, not for ordinary decoration.
- Moderate corner radius and restrained motion: youthful, not childish.
- Do not use a generic purple AI gradient.
- Teacher views may be denser; Student views prioritize one clear next action.
- Typography and final token values are selected in M1 and recorded as design tokens, not scattered literals.

## 3. Route map

Planned frontend routes:

| Route | Access | Purpose |
|---|---|---|
| `/` | Public | Product introduction and Studio entry |
| `/access` | Public | Studio access-code form |
| `/studio` | Studio session | Dashboard, role switch, template, agent list |
| `/studio/reviews` | Studio session | Submitted and approved Agent review queue |
| `/studio/published` | Studio session | Currently published Agent directory and management links |
| `/studio/agents/:agentId` | Studio session | Single-page Agent Workspace |
| `/studio/review/:agentId` | Teacher role | Evaluation, evidence, versions, approval, publishing |
| `/p/:slug` | Public | Published agent experience |

No settings center, account page, class-management page, or general admin UI is in scope.

## 4. Shared navigation

### Studio shell

- AgentSprout wordmark
- active links for Workshop, Reviews, and Published; no disabled placeholder navigation
- current role and explicit Student/Teacher switch
- current environment indicator only in development
- session-expiry handling
- no public display of access code or internal secrets

The role switch changes a server-side demo-session role; it is not a client-only visual toggle.

### Public shell

- lightweight AgentSprout identity
- link explaining the concept and privacy behavior
- no link exposing Studio access by default

## 5. Screen specifications

### 5.1 Access

Required elements:

- access-code field
- show/hide control
- submit button
- concise explanation that this is a protected concept Studio
- invalid-code, expired-session, rate-limit, network-error, and server-error states

Success sets a Secure HttpOnly session cookie and redirects to `/studio`. The access code must never be placed in localStorage, a URL, analytics, or logs.

### 5.2 Dashboard

The Studio shell exposes three URL-backed dashboard views that reuse the same session and
agent-list request:

- **Workshop** (`/studio`) shows the creation template and every Agent's current working version.
- **Reviews** (`/studio/reviews`) shows current versions in `IN_REVIEW` or `APPROVED`, with
  links into the existing Teacher Review experience. It has a clear empty queue state.
- **Published** (`/studio/published`) shows Agents with a current published version, even when
  the same Agent also has a newer Draft. Each card links to the public Agent and its review/
  withdrawal controls. It has a clear no-live-agents state.

The selected sidebar destination uses `aria-current="page"`. Role switching keeps the user
in the selected view and refreshes its server-authoritative actions.

Student mode:

- Knowledge Explorer template card
- disabled "Coming soon" treatment only if needed for visual balance; no Pathfinder implementation
- `Create agent` action
- agent cards showing name, latest version, lifecycle state, knowledge status, and next action
- empty state that leads directly to the template

Teacher mode:

- agents awaiting review first
- evaluation status and publish readiness
- no creation action

Creation form fields follow `docs/PRD.md`. Inline validation must match server validation.

### 5.3 Agent Workspace

One route with four sequential stage tabs. Only the selected stage panel is visible, while
the other panels remain mounted so an in-progress upload, unsaved form state, and the current
Playground conversation are not discarded when the user changes stages:

1. **Define** — problem, intended users, audience age, success goal, welcome message, tone, length, custom instructions.
2. **Knowledge** — file requirements, selected file, checksum/dedup result, persisted ingestion stages, failure reason, retry.
3. **Test** — chat, real processing stages, citations, safety-example buttons, simplified result category.
4. **Submit** — version summary, change reflection for v2+, readiness checklist, submit action.

Rules:

- The selected stage is stored in the URL fragment (`#define`, `#knowledge`, `#test`, or
  `#submit`). Refresh and browser Back/Forward restore the selected unlocked stage.
- Define and Knowledge are always selectable. Test and Submit are disabled until knowledge
  is Ready; a stale URL targeting a locked stage returns to Knowledge.
- The four-stage navigation exposes the selected and disabled states to assistive technology,
  and switching stages moves focus to the newly displayed panel without a full-page reload.
- A user cannot test before knowledge is Ready.
- A user cannot submit while ingestion or a chat run is active.
- Double submission is prevented client- and server-side.
- Refresh restores the active version, ingestion job, and Studio chat history.
- Once submitted, controls become read-only and explain why.

### 5.4 Playground

The Playground does not stream raw model tokens. It displays backend-reported stages:

- Checking safety
- Searching the knowledge base
- Preparing an age-appropriate answer
- Verifying citations

Answer display includes:

- final safe response
- citation chips
- expandable citation excerpt with filename and page
- result label for blocked, guided, refused, or answered
- retry for transient failure only

Safety example buttons populate representative prompts but require the Student to send them. They do not inject hard-coded results.

### 5.5 Teacher Review

Required sections:

- submitted version summary and student reflection
- Run evaluation action
- real `completed / 16` progress with current status
- metric cards and release-gate result
- filterable case table
- failure detail showing sanitized input, safe output, expected rule, retrieval evidence, and judge rationale
- sanitized LangGraph trace drawer
- model IDs, latency, token use, and estimated cost
- completed v1/v2 run selector and comparison
- required feedback field for Request changes
- Approve, Publish, and Withdraw actions with server-authoritative eligibility

No score may be edited manually.

### 5.6 Published Agent

Required content:

- project name
- problem, intended users, and success goal
- audience-age label
- Approved badge and published version
- welcome message
- public chat
- citations
- privacy reminder
- rate-limit and temporary-failure states
- attribution for the NOAA knowledge source when the demo asset is used
- anonymous builder label: `Student Builder`

Do not show the child's name, custom system instructions, Studio traces, evaluation cases, scores, or unpublished versions.

## 6. Component state contract

Every component that calls an API must explicitly implement applicable states:

- initial/idle
- loading or queued
- empty
- success
- client validation error
- 401 session required
- 403 role or state denied
- 404 missing resource
- 409 conflict or duplicate active job
- 413 file too large
- 422 unsupported or invalid input
- 429 rate limited with retry time
- transient network/server error
- timeout
- disabled/submitting
- safe retry

Raw stack traces, provider error bodies, and secrets are never rendered.

## 7. Responsive behavior

### Studio

- Desktop-first, minimum supported width 1024 px.
- Supported on current Chrome, Edge, and Safari.
- Below 1024 px, show a purposeful message recommending a laptop or landscape tablet; do not compress the full builder into an unusable layout.

### Published Agent

- Fully responsive from 375 px.
- Chat input remains reachable with the mobile keyboard open.
- Citations open without horizontal overflow.
- Primary content remains usable on mobile, tablet, and desktop.

## 8. Accessibility baseline

- WCAG AA color contrast for text and controls.
- Semantic landmarks, headings, labels, buttons, and tables.
- Visible focus indicators.
- Full keyboard access for accepted flows.
- Error messages programmatically associated with fields.
- Status is never conveyed by color alone.
- ARIA live regions for chat stages, upload status, evaluation progress, and errors.
- `prefers-reduced-motion` respected.
- Focus moves to meaningful content after modal submit, route transition, and validation failure.
- Playwright covers Chromium; Published Agent critical flow also covers WebKit and a 375 px viewport.

## 9. Content rules

- Product UI is English-only in the MVP.
- Use plain, specific verbs: Create, Upload, Test, Submit, Evaluate, Approve, Publish.
- Explain blocked actions rather than only disabling them.
- Do not claim that evaluation guarantees safety.
- Do not claim production readiness for unsupervised child use.
- Do not use manipulative streaks, leaderboards, or public student rankings.

## 10. Screenshot acceptance

Store final acceptance screenshots outside runtime data for:

- Student Dashboard
- Agent Workspace with Ready knowledge
- Playground with citations and one blocked case
- Teacher Review with evaluation results and v1/v2 comparison
- Published Agent desktop
- Published Agent mobile

Screenshots must contain no real secrets, access codes, PII, or identifying child data.
