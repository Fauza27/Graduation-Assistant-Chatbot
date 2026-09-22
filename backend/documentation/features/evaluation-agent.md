# Evaluation agent: evidence and diagnosis

## Purpose

The agent audits saved chatbot requests against the original academic guides.
It identifies evidence and proposes changes supported by the recorded pipeline.
It does not edit guides, change production settings, or apply recommendations.
The admin starts a batch; there is no scheduler.

## Findings from the 21 September 2026 run

Run `4b6bd7e7-4fde-4883-9848-4f40efb5e075` completed with 107 cases,
33 positive evidence decisions and 74 unresolved cases. These are **not accuracy
scores**. Several positive decisions used a different academic track, while
several negative decisions quoted the answer and still rejected it.

The implementation had these concrete weaknesses:

1. Three independently generated booleans allowed contradictory evidence decisions.
   The verification prompt emphasized scope rejection without equivalent positive
   examples. The output did not require a reference answer.
2. Recorded reformulations replaced students' original questions in context and
   domain routing. Old mistakes such as appending KKP to a publication question
   therefore contaminated the evaluator too.
3. Only three recent turns supplied domain context. Earlier explicit track names
   disappeared during longer conversations.
4. LLM-generated evidence text and page numbers were accepted without checking
   the source. Out-of-range pages were silently clamped.
5. Word-set overlap on child chunks was treated as proof of extraction loss or
   faulty splitting; the actual parent text was not checked.
6. Any filter was blamed when retrieval missed. Retrieving a sibling child of
   the correct parent could also be incorrectly labeled a retrieval failure.
7. Related-scope evidence still triggered diagnostic generation, producing advice
   to change official guide content even without verified evidence.
8. Entering the queue was treated as proof the chatbot answer was wrong.
9. Rejected candidate decisions were not retained, making failures hard to audit.

## Current flow

1. Load selected cases, request traces and preceding turns from the same session.
   Keep the historical rewrite for diagnosis. Use original student questions for
   evidence search and prompts. Earlier questions preserve domain context; the
   prompt includes at most the last 20 questions. Chatbot answers are not a source
   of academic facts or domain routing.
2. Analyze questions per conversation session before reading a guide. Resolve
   references, select one or more document domains, classify comparison questions,
   and split the question into atomic information needs. Explicit domains from the
   student cannot be removed by the model. Ambiguous or low-confidence routing is
   widened instead of silently excluding a possible guide.
3. Process one routed document at a time and only search questions assigned to that
   document. Read and cache all original pages in that guide, then select a bounded
   number of page windows per question. Multi-document questions retain a separate
   information need for every compared guide.
4. Verify candidates with one verdict: `supported`, `partial`, `related_scope`, or
   `not_found`. Require a verbatim quote, physical page range and a reference
   answer. The verifier must identify the information needs covered by the quote
   and separately check subject, requested attribute, academic scope and unit.
5. Check that the quote occurs on the cited pages. Reject fabricated/paraphrased
   quotes, invented numbers, invalid pages, inconsistent verdicts and semantic
   mismatches such as total days being used as daily hours. A question is verified
   only after every required information need has evidence. Save each attempt and
   its rejection reason.
6. Compare every verified quote against **both child and parent text**, preserving word
   order, numbers and negations while ignoring formatting. Exact matches support
   tracing evidence through production. Mere lexical similarity remains a hint,
   not proof that extraction or chunking is broken.
7. Assess the saved chatbot answer against the combined verified evidence. A correct or
   uncertain answer receives no automatic repair recommendation. The existing
   database stage `unknown` represents no established failure for a correct
   answer; `answer_assessment.verdict` in diagnostics states `correct` explicitly.
8. Trace observed evidence through retrieval, parent assembly, reranking and final
   context. A sibling child can retrieve the right parent. Missing trace fields
   mean unknown, rather than an empty successful stage. Conflicting academic
   domains in the recorded rewrite are explicit query-processing evidence.
9. Request at most two recommendations only when the diagnosis is supported.
   Enforce the observed failure stage and accept targets from inspected code or
   known configuration only. Never generate document-edit advice for unresolved
   evidence. Keep model confidence no higher than the underlying diagnosis.
10. Persist the question plan, evidence coverage, report and diagnostics. Equal question text is reported separately
   from case count, because two requests can have different conversation contexts.

Source search and verification are separate: quotation validation proves source
provenance, **not semantic correctness**. A supported LLM verdict still needs
human calibration before being used as a research label. The agent deliberately
does not assert that information is absent from an entire guide after checking
only a subset of candidate windows.

## Implementation map

| Responsibility | Module |
| --- | --- |
| Saved cases, raw session context, paginated chunk reads | `src/evaluation_agent/repository.py` |
| Original page extraction and caching | `src/evaluation_agent/document_reader.py` |
| Conversation-aware soft document routing | `src/evaluation_agent/question_planner.py` |
| Original-page candidate search within routed documents | `src/evaluation_agent/evidence_search.py` |
| Typed evidence/answer decisions | `src/evaluation_agent/models.py` |
| LLM verification, answer assessment and review | `src/evaluation_agent/model_client.py` |
| Quote/page validation | `src/evaluation_agent/evidence_validation.py` |
| Child and parent comparison | `src/evaluation_agent/chunk_auditor.py` |
| Recorded-stage diagnosis | `src/evaluation_agent/trace_analyzer.py` |
| Recommendation constraints | `src/evaluation_agent/review_policy.py` |
| Orchestration and per-run evidence/chunk caches | `src/evaluation_agent/runner.py` |
| Human report and machine-readable diagnostics | `src/evaluation_agent/report.py` |

Existing database columns are preserved. Question plans, information-need coverage,
evidence attempts, reference answers, historical rewrites and answer assessments use the existing diagnostics
JSON and local report JSON. No SQL migration is required for these changes.
Historical reports are preserved and not relabeled as improved results.

## Validation and operating cost

Run offline tests with the project's virtual environment:

```powershell
.\virtual_environment\Scripts\python.exe -m pytest tests -q
.\virtual_environment\Scripts\python.exe -m scripts.check_evaluation_search
```

The second command reads local PDFs and checks 12 candidate-search cases against
verbatim excerpts on known physical pages. It makes no model or database calls.
Some fixtures explicitly supply track context to test routing; this does not
claim that every historical request originally included that context. The
22 September offline result was 12/12 expected pages within eight candidates,
with all fixture quotes confirmed in the source PDFs.

Unit tests cover source provenance, contradictory decisions, domain drift,
parent retrieval through siblings, missing traces, correct answers, and blocked
unsupported recommendations. Mock model tests verify software behavior, not the
LLM's semantic accuracy. Paid re-evaluation is a separate validation step and was
not run as part of this repair.

Validation on 22 September: **253 backend tests passed**, with three existing
dependency deprecation warnings; Ruff checks passed. No production database data
or historical evaluation reports were changed during these offline checks.

Verified cases now use an additional answer-assessment call. Unresolved cases
skip diagnostic generation. Within a run, identical questions with identical
student context/domain reuse evidence checks; each incident still receives its
own answer/trace diagnosis. Chunk and parent reads are cached per document version.
Actual cost depends on candidate checks and cannot be inferred from these tests.

OpenAI's [Structured Outputs guidance](https://developers.openai.com/api/docs/guides/structured-outputs)
explains the schema boundary; semantic correctness still requires application
validation and evaluation on representative cases.
