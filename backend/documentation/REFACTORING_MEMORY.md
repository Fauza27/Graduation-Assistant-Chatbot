# Refactoring Memory

## Purpose

### Chatbot repair — 22 September 2026

- User stopped agent development and requested direct diagnosis/repair of RAG.
- Read-only snapshot: 163 traces from 20 sessions; 85 empty contexts caused by
  absolute reranker gate; 43 rewritten requests still reranked on raw input.
- Changed contextual reformulation, resolved rerank query, optional absolute
  gate, source/parent-aware dedup, and evidence-only generation instructions.
- Existing unrelated agent changes remain untouched. No SQL/database writes.
- Live 18-question replay stopped on first question: `credit_balance_exhausted`.
  No successful post-fix answer; do not claim measured quality improvement.
- Final validation: 261 tests pass, targeted Ruff and diff checks pass.
- Details and remaining verification: `development/chatbot-repair-20260922.md`.

### Evaluation repair — 22 September 2026

- Inspected completed run `4b6bd7e7-4fde-4883-9848-4f40efb5e075`: 33 positive
  evidence decisions / 107 cases are not accuracy. Old rewrites contaminated
  context; evidence booleans and unvalidated quotes caused false decisions.
- Current work repairs evaluation only: raw student context, one evidence verdict,
  strict quote provenance, parent-aware audit, answer assessment, trace and
  recommendation guards, audit trail and offline regression tests.
- See `documentation/features/evaluation-agent.md` for design and limitations.
- Local original-PDF candidate-search benchmark: 12/12, no paid API calls.
- Final backend validation: 245 tests passed; Ruff passed. Three existing dependency
  deprecation warnings remain. Semantic LLM accuracy has not been remeasured.
- Do not run a paid batch again until the user's instruction. Preserve old reports.
- The user confirmed the prior SQL migration was executed; the older pending
  note below is historical. This repair does not require another migration.

This file records the decisions, boundaries, and verification status for the
ongoing refactor. It is the single working-memory file requested for this
work, so future changes can continue without repeating discovery.

## Goal

Make the backend easier to read, navigate, test, and maintain while preserving
the current API contracts, database schema, retrieval behavior, and runtime
performance.

## Scope

- Refactor `backend/src`, configuration, scripts, tests, and application
  documentation.
- Preserve external behavior unless a defect is found and covered by tests.
- Do not refactor `src/bot`, `src/ingestion`,
  `src/generation/intent_classifier/ga_dibutuhin_lagi`, or `classifier.py`.
- Do not execute database migrations during this refactor. Migration
  `2026092101_evaluation_soft_failures.sql` remains pending user execution.

## Baseline

- Baseline commit: `2ef8dd0` (`feat(rag): improve evaluation and retrieval reliability`).
- Test baseline: `200 passed` with three existing dependency deprecation
  warnings.
- Application entry point: `application.py`; server entry point: `main.py`.

## Refactoring Rules

1. Prefer small named functions and explicit data models over long procedural
   methods.
2. Keep I/O at module boundaries; keep data transformations deterministic and
   testable.
3. Avoid abstractions that hide simple logic or add runtime cost without a
   clear benefit.
4. Keep public function names and API response shapes stable unless tests and
   documentation are updated together.
5. Run the relevant focused tests after each slice, then the full backend test
   suite before committing a completed slice.

## Current Inventory

- 67 Python files in scope.
- Highest-priority large modules: retrieval pipeline, self-query, AI service,
  session storage, evaluation-agent repository and runner, and legacy RAGAS
  evaluators.
- Existing `docs/` contains historical and feature notes. New documentation
  will live in `documentation/` and use a stable, role-based structure.

## Completed Slices

- Application lifecycle, chat orchestration helpers, health endpoints, and
  session API readability. Health checks now use a monotonic timer and run the
  synchronous Supabase probe off the event loop. Focused validation: 48 tests
  passed.
- Initial maintained documentation structure under `documentation/`.
- Session-list title generation and message serialization are now pure shared
  functions, used by database and in-memory session strategies. Their output
  is covered by unit tests.

## Next Slice

Establish the new documentation structure and refactor low-risk composition
code first: application lifecycle, shared constants, and simple module
boundaries. Then proceed through retrieval, sessions, evaluation, and API
layers in separately tested commits.
