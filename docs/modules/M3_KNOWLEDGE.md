# M3 — Knowledge Ingestion and Retrieval

## Status

Pending M2 acceptance.

## Vertical outcome

The Student uploads the official NOAA PDF from the Workspace, sees real asynchronous stages, recovers from supported failures, and proves persistent page-aware retrieval through Chroma using real OpenAI embeddings.

## Prerequisites

- User creates local `.env` and provides `OPENAI_API_KEY` there, not in chat.
- Recheck the official NOAA repository record and license.
- Resolve and record original-PDF commit versus checksum download-script strategy.

## Frontend scope

- Workspace Knowledge section.
- File picker/drop target with extension/size guidance.
- Client validation that mirrors but does not replace server validation.
- Real stage display: Uploaded, Extracting, Chunking, Embedding, Ready, Failed.
- Known batch progress where reported.
- Duplicate result, retryable/non-retryable error, and Retry behavior.
- Lock Test/Submit sections until Ready.
- Refresh restores job/document state.
- Failed replacement visibly retains the prior Ready document.

## Backend scope

- Secure multipart upload and filename/path handling.
- 15 MB, 100 page, MIME/extension, PDF encryption/text checks.
- SHA-256 computation and duplicate handling.
- Page-aware PDF extraction plus TXT/Markdown extraction.
- Paragraph-aware deterministic chunking with stable IDs.
- Official OpenAI embedding batch adapter and timeout/retry policy.
- Persistent Chroma collection/metadata and exact version/document filtering.
- Staged replacement, atomic active-document switch, and compensating cleanup.
- In-process job, heartbeat/status, one-workspace concurrency, restart failure recovery, and idempotent retry.
- Retrieval service returning top four and threshold decision; no generation yet.

## Data scope

- `knowledge_documents`
- `ingestion_jobs`
- active-document linkage
- Chroma `knowledge_chunks`
- upload file tree
- ingestion quotas/rate buckets

## API scope

- upload, ingestion status, retry, and Draft deletion endpoints
- no successful chat endpoint yet
- internal retrieval verification may use tests/diagnostics, not a public production endpoint

## NOAA source work

- Download unchanged official PDF.
- Fill `docs/KNOWLEDGE_SOURCE.md` verification record.
- Verify byte size/page count/text extraction.
- Record source/license/checksum.
- Ensure chosen repository strategy is reproducible.

## Automated checks

- all ingestion fixtures in `docs/TEST_STRATEGY.md`
- stable page/chunk IDs
- no duplicates after retry
- previous Ready document preservation
- restart marks unfinished job failed
- exact Chroma metadata filter
- real embedding opt-in test
- frontend upload states and refresh restoration
- Playwright upload success plus one retryable/non-retryable failure

## Manual verification

1. Upload official NOAA PDF.
2. Observe each real state and record duration.
3. Refresh during processing and after Ready.
4. Verify known question retrieval includes relevant NOAA pages.
5. Upload duplicate.
6. Exercise invalid/scanned fixture.
7. Simulate/reproduce retryable provider failure through test environment and confirm no duplicates.
8. Restart and verify Ready knowledge remains queryable.

## Acceptance mapping

- `ACC-KNW-001`
- `ACC-KNW-002`
- `ACC-KNW-003`
- persistence portion of `ACC-FND-002`

## Non-goals

- LLM answer generation
- LangGraph chat
- evaluation cases
- multi-file, OCR, web crawling, or independent vector service

## Exit gate

- [ ] NOAA source record is complete and license rechecked.
- [ ] Real upload-to-Ready browser flow passes.
- [ ] Real embedding and page-aware retrieval smoke tests pass.
- [ ] Failure/retry/restart/preservation tests pass.
- [ ] M1–M2 regressions pass.
- [ ] No raw upload is public or outside validated data paths.
- [ ] Evidence is recorded before moving to M4.
