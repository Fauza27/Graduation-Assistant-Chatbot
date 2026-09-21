# RAG, Conversation Memory, and Evaluation

## Retrieval

For each question, the query planner can normalize or reformulate the query.
The retrieval pipeline then parses source and section filters, runs hybrid
search, assembles parent chunks around matching child chunks, and reranks the
parent candidates. The answer generator receives only accepted context.

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

The evaluation agent processes queued cases in batches. It reads original
documents by page window, distinguishes direct evidence from evidence with a
different scope, audits the relevant chunks, and records a diagnosis and
recommendation for an administrator to review.

An answer that correctly says a detail is unavailable can still enter the
queue when related information exists in a narrower scope. This identifies
answers that are factually careful but not sufficiently helpful, without
turning a scope difference into a false retrieval defect.
