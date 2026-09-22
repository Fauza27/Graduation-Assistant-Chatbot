# RAG, Conversation Memory, and Evaluation

## Retrieval

For each question, the query planner can normalize or reformulate the query.
The retrieval pipeline then parses source and section filters, runs hybrid
search, assembles parent chunks around matching child chunks, and reranks the
parent candidates. The answer generator receives only accepted context.

Follow-up questions without an explicit domain also go through reformulation.
The rewriter resolves the question's subject, academic stage, and track from
the conversation. User messages take precedence over possibly wrong assistant
answers. Both search and reranking use the resolved question. The original
student question remains the input to answer generation and the audit log.

`rerank_min_top_score` is optional and disabled by default. Negative raw scores
do not prove that the guides lack an answer. Relative-gap selection and top-N
still bound the context; the generator must check whether that context supports
the requested claim. Enabling an absolute cutoff requires calibration against
answerable and unanswerable questions for the selected model.

Identical child text is deduplicated only within the same source and parent,
so a comparison can retain evidence from both PI and KKP.

The reranker uses the matched child evidence when available so a relevant part
of a long parent chunk is not hidden by an unrelated opening section.

## Two-level memory

`ConversationMemory` stores:

1. A compact summary of older complete exchanges.
2. Recent user and assistant turns.

When token usage exceeds the configured budget, complete older exchanges are
summarized by the configured LLM. The summary and recent turns are sent with
the next generation request. The database stores the durable conversation;
the LRU session cache is only an in-process speed optimization.

## Evaluation agent

The evaluation agent processes queued cases in batches. It reconstructs a
self-contained question from the recorded query plan and prior session turns,
then builds a deterministic BM25 index over every original-document page window.
An LLM verifies only the best candidates for one case at a time. Verified evidence
is compared with active chunks and the request trace before a diagnosis and
recommendation are recorded for an administrator to review.

Failure to verify a candidate is recorded as inconclusive. It is not treated as
proof that the documents lack the requested information. This prevents the agent
from recommending document changes when its own evidence search was uncertain.

An answer that correctly says a detail is unavailable can still enter the
queue when related information exists in a narrower scope. This identifies
answers that are factually careful but not sufficiently helpful, without
turning a scope difference into a false retrieval defect.
