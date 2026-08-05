# Interview Demo Runbook

## 1. Goal

Demonstrate in approximately five minutes that AgentSprout is a real full-stack agent product with knowledge ingestion, child-safety routing, evaluation, versioning, and deployment—not a scripted chatbot.

## 2. Pre-demo preparation

- Complete the interview-day checklist in `docs/DEPLOYMENT.md`.
- Reset the temporary Studio workspace.
- Keep the fixed published sample available as a fallback proof of deployment.
- Have the official NOAA PDF locally available.
- Verify OpenAI quota and both live URLs.
- Privately retain the Studio access code.
- Open browser tabs for GitHub README, Studio access, and fixed published sample.
- Do not place secret values or admin endpoints on screen.

## 3. Primary walkthrough

### 0:00–0:30 — Product framing

Open Studio and state:

> AgentSprout lets students build grounded AI products, lets teachers evaluate them with reproducible evidence, and only publishes versions that pass safety gates.

Show the role switch and Knowledge Explorer template.

### 0:30–1:10 — Define and upload

- Create Ocean Explorer.
- Show Problem, Intended users, Success goal, and audience age.
- Upload the unchanged NOAA PDF.
- Point out the real persisted ingestion stages, SHA-256 deduplication, and page-aware embedding.
- While processing, explain that business state is SQLite and vectors are embedded Chroma on a persistent Railway volume.

If the official PDF cannot finish within the target, do not fake Ready. Open the fixed prepared sample and identify the live ingestion delay honestly.

### 1:10–2:00 — Grounded answer

- Ask one known in-document ocean-literacy question.
- Show real safety, retrieval, generation, and validation stages.
- Open a citation and show filename, page, and supporting excerpt.
- Ask one demonstrably out-of-knowledge question and show refusal to use model memory.

### 2:00–2:40 — Safety behavior

- Use the synthetic privacy example and show that it is blocked before provider/persistence.
- Use the homework request and show guided learning rather than ghostwriting.
- Use the prompt-injection example and show policy/knowledge-boundary resistance.
- Switch briefly to Teacher trace and show sanitized route evidence, not hidden prompts.

### 2:40–3:40 — Evaluation

- Submit the immutable version.
- Switch to Teacher.
- Start the 16-case evaluation.
- Show real three-concurrent progress, categories, model snapshots, latency, tokens, and a failure detail.
- Explain that safety categories require 100% and errors block release.

If the run is still active, use a previously completed immutable run for the remaining UI walkthrough and explicitly identify it as a prior run. Never imply an unfinished run completed.

### 3:40–4:30 — Version improvement

- Show a changes-requested v1 and v2 reflection.
- Compare selected completed runs using the same suite and model baseline.
- Highlight a case transition and cost/latency delta, not only the total score.

### 4:30–5:00 — Approve and publish

- Show that a failed version cannot be approved.
- Approve a release-eligible version and publish it.
- Open the mobile-friendly public slug.
- State that public chat is rate limited, stores no full transcript, and cannot access Studio APIs.

## 4. Technical questions to anticipate

### Why older models?

The workload is bounded RAG and structured classification. `gpt-4o-mini` handles online volume; `gpt-4.1-mini` is used only for lower-frequency rubric judgment. Model upgrades must earn their cost through the fixed eval suite.

### Why SQLite and Chroma?

They minimize demo infrastructure while still separating transactional and vector concerns. The one-instance/one-volume scaling boundary is explicit; managed Postgres/network vector storage is a documented production migration.

### Why no token streaming?

Child-facing output must pass complete moderation and citation validation before display. The UI streams/polls real stages, not unchecked tokens.

### Why LangGraph?

The safety and RAG flow has explicit branches, observable nodes, and testable stop conditions. It is not used merely as a wrapper around one prompt.

### Is the product ready for children?

No. It is a supervised concept MVP. Production requires identity, consent, school safeguarding, legal/privacy review, durable jobs, managed storage, and incident operations.

## 5. Failure handling during interview

- Provider timeout: show the honest retryable state and use a previously completed run for inspection.
- cloud cold start: use the wait to show GitHub architecture, then recheck `/ready`.
- rate limit: do not raise limits in code; use independent Studio allowance or reset approved demo buckets through documented admin operation.
- ingestion failure: show error/retry and use the fixed sample; never manually mark Ready.
- evaluation failure: show persisted completed cases and explain why infrastructure errors block publishing.

## 6. Post-demo links

README must provide:

- live public Demo
- repository
- architecture and safety documentation
- setup instructions
- explicit independent-concept disclaimer

Studio access code is shared privately, not in README.

