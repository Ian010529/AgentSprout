# Product Requirements Document

## 1. Product summary

AgentSprout Studio is a rapid agent creation, evaluation, and publishing product for supervised AI education. It demonstrates a complete product loop rather than a standalone chatbot:

```text
Define a problem → Build an agent → Add knowledge → Test safety
→ Submit → Evaluate → Reflect and revise → Approve → Publish
```

The interview MVP is deliberately narrow: one Knowledge Explorer template, one knowledge file per version, two audience-age modes, one supervised Studio workspace, and one public published agent experience.

## 2. Product goals

- Let a student build a useful RAG agent without exposing model or infrastructure settings.
- Make responsible AI behavior visible through privacy, homework, injection, moderation, and grounding controls.
- Give a teacher reproducible evidence instead of a subjective "looks good" approval.
- Demonstrate rapid prototyping, full-stack product delivery, evaluation ownership, and real deployment.
- Complete the canonical interview demo in less than five minutes after document ingestion is ready.

## 3. Non-goals

The MVP does not include:

- real user registration, OAuth, school accounts, classrooms, or parent accounts
- multi-tenancy or production identity and access management
- payments, subscriptions, notifications, email, or SMS
- multiple agent templates beyond Knowledge Explorer
- multi-agent orchestration, MCP, browsing, voice, image generation, or code execution
- foundation-model training, fine-tuning, or custom model hosting
- drag-and-drop workflow building
- real-time collaboration
- OCR for scanned PDFs or semantic interpretation of complex tables and images
- multi-file knowledge bases, website crawling, or source synchronization
- multilingual UI or answer modes
- native mobile applications or offline support
- a real school safeguarding or emergency-notification system

## 4. Users and roles

### Student

The Student is a supervised builder. They can create an agent, edit a draft, upload knowledge, test it, save a new version with reflection, submit it, and inspect teacher feedback and evaluation results.

### Teacher

The Teacher can inspect submitted versions and sanitized traces, run evaluation, request changes, approve passing versions, publish an approved version, and withdraw a publication.

### Public visitor

The visitor can use the published agent subject to rate limits. They cannot see Studio configuration, traces, evaluation details, unpublished versions, or mutation APIs.

### Demo administrator

The administrator can run an out-of-band reset command protected by a separate secret. There is no reset button in the product UI.

## 5. Canonical product journey

1. A visitor enters a Studio access code.
2. The Student role opens the Dashboard.
3. The Student chooses the Knowledge Explorer template.
4. The Student creates **Ocean Explorer**.
5. The Student supplies:
   - Project name
   - Problem to solve
   - Intended users
   - Audience age: 7–11 or 12–17
   - Success goal
   - Welcome message
   - Tone: Friendly, Curious, or Coach-like
   - Response length: Short or Balanced
   - Optional custom instructions, maximum 500 characters
6. The Student uploads one supported knowledge file.
7. The UI shows persisted ingestion stages until the document is Ready.
8. The Student asks a normal question and receives a grounded, age-appropriate answer with citations.
9. The Student exercises four visible safety examples:
   - out-of-knowledge question
   - personal address or contact information
   - homework ghostwriting request
   - prompt-injection request
10. The Student submits the immutable version.
11. The Teacher runs the fixed 16-case evaluation.
12. The Teacher reviews metrics, failure evidence, retrieval chunks, latency, token use, and node trace.
13. If changes are requested, the submitted version stays immutable and the Student creates the next draft version.
14. The Student records what changed and why.
15. The Teacher compares completed v1 and v2 evaluation runs using the same cases and model baseline.
16. A passing version is approved and published.
17. The published slug opens a read-only, mobile-friendly agent page.

## 6. Student-editable configuration

Students may edit only a Draft version:

- project name
- problem to solve
- intended users
- audience age
- success goal
- welcome message
- tone
- response length
- custom instructions, up to 500 characters
- knowledge file

Students may not edit:

- system safety rules
- privacy detectors
- moderation configuration
- model IDs or model parameters
- retrieval threshold or top-k
- evaluation cases, rubrics, or release thresholds
- system prompt text
- role permissions or rate limits

## 7. Age modes

### Ages 7–11

- short sentences and common vocabulary
- maximum target response length: about 120 English words
- one core concept per answer
- concrete analogies and an encouraging follow-up question where useful
- unfamiliar terms explained immediately
- homework guidance limited to one hint, one explanation step, and one guiding question

### Ages 12–17

- introductory technical vocabulary with first-use explanation
- maximum target response length: about 220 English words
- structured steps and limited technical detail
- homework guidance may include an approach, checklist, and feedback on the student's attempt, but not a submission-ready answer

Both modes use English in the MVP and must remain grounded in the uploaded document.

## 8. Knowledge requirements

- Exactly one file per agent version.
- Supported types: PDF, TXT, Markdown.
- Maximum size: 15 MB.
- Maximum pages for PDF: 100.
- Text-based PDFs only. Scanned, encrypted, corrupted, or effectively empty PDFs fail with a clear error.
- The source document is immutable once its version is submitted.
- Citations identify the file, page number where applicable, and supporting excerpt.
- Insufficient retrieval evidence results in an explicit knowledge-boundary refusal.

## 9. Safety behavior

Five user-visible routes are required:

1. **PII:** contact details and detailed addresses are blocked before model invocation and persistence; the raw input is neither logged nor echoed.
2. **Homework ghostwriting:** the agent teaches through hints and questions rather than producing submission-ready work.
3. **Prompt injection:** the agent does not reveal or override internal rules and redirects to the knowledge topic.
4. **Unsafe content:** OpenAI Moderation and product rules produce a short, non-graphic, age-appropriate response. Immediate danger or self-harm responses recommend contacting a trusted adult or local emergency service.
5. **Out of knowledge:** the agent states that the uploaded material does not provide enough information and does not fill the gap from model memory.

This MVP does not claim to replace a teacher, counselor, safeguarding lead, or emergency service.

## 10. Evaluation and release gate

The fixed suite contains 16 cases:

- 4 in-knowledge questions
- 3 out-of-knowledge questions
- 3 privacy cases
- 2 homework-ghostwriting cases
- 2 prompt-injection cases
- 2 age-appropriateness cases

Release thresholds:

- privacy, safety, and injection: 100%
- out-of-knowledge refusal: 100%
- grounded knowledge answers with valid citations: at least 75%
- average age appropriateness: at least 4/5
- average instruction following: at least 4/5
- no unresolved evaluation infrastructure error

Any blocking failure prevents approval and publication.

## 11. Version and publication lifecycle

Formal version states are:

```text
DRAFT → IN_REVIEW → APPROVED → PUBLISHED
            ↓
    CHANGES_REQUESTED → next DRAFT version

PUBLISHED → WITHDRAWN
```

- A Draft may be edited in place until submission.
- Submission makes that version immutable.
- Requesting changes does not unlock the submitted version; the next version is copied into a new Draft.
- A new version requires `what_changed` and `why_changed`.
- Publishing a new version does not happen automatically when it is approved.
- The current published version remains available until a replacement is explicitly published.
- Only one version of an agent is publicly active at a time.

## 12. Success metrics

The MVP is accepted when:

- the complete canonical flow works through the browser using real APIs
- the fixed NOAA PDF produces page-valid citations
- PII canary tests prove no blocked raw input reaches OpenAI or persistence
- all blocking evaluation categories pass for the publishable demo version
- v1/v2 comparison uses identical cases and model snapshots
- public mutation and Studio-internal access attempts fail server-side
- data survives a Railway redeploy
- the complete prepared interview walkthrough takes less than five minutes
- the repository contains no secrets, runtime data, or hard-coded evaluation results

## 13. Product constraints

- Quick interview MVP, not production deployment to children.
- Real OpenAI API calls only in runtime.
- One backend instance because SQLite and embedded Chroma are single-volume resources.
- No horizontal replicas in the MVP.
- Studio requires a shared access code; this is explicitly not real authentication.
- Public use is cost- and abuse-limited.
