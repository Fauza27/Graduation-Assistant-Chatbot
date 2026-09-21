"""Cross-encoder reranking for retrieved documents."""

from __future__ import annotations

import os
import threading
from typing import Any

from loguru import logger

from config.settings import get_settings

DEFAULT_MAX_CONTENT_CHARS = 2000


class CrossEncoderReranker:
    """
    Rerank documents using a cross-encoder relevance model.

    The ranking score comes exclusively from the cross-encoder.
    No manual keyword boost is applied.
    """

    _shared_model: Any = None
    _shared_model_name: str | None = None
    _model_lock = threading.Lock()

    def __init__(
        self,
        model_name: str | None = None,
        max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
    ) -> None:
        settings = get_settings()

        self.model_name = model_name or settings.cross_encoder_model

        self.top_n = settings.rerank_top_n
        self.max_content_chars = max(
            1,
            max_content_chars,
        )

        self._configure_huggingface_token(settings.hf_token)

    @staticmethod
    def _configure_huggingface_token(
        hf_token: str | None,
    ) -> None:
        """Configure Hugging Face authentication when available."""

        if not hf_token:
            return

        os.environ.setdefault(
            "HF_TOKEN",
            hf_token,
        )

        os.environ.setdefault(
            "HUGGINGFACE_HUB_TOKEN",
            hf_token,
        )

    def _get_model(self) -> Any:
        """
        Return the shared cross-encoder model.

        Model initialization is lazy and thread-safe.
        """

        cls = type(self)

        if cls._shared_model is not None and cls._shared_model_name == self.model_name:
            return cls._shared_model

        with cls._model_lock:
            if cls._shared_model is None or cls._shared_model_name != self.model_name:
                from sentence_transformers import (
                    CrossEncoder,
                )

                logger.info(
                    "Loading cross-encoder model: {}",
                    self.model_name,
                )

                cls._shared_model = CrossEncoder(self.model_name)

                cls._shared_model_name = self.model_name

                logger.info("Cross-encoder model loaded.")

        return cls._shared_model

    def warmup(self) -> None:
        """Pre-warm the model into memory to avoid cold start delays."""
        self._get_model()

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_n: int | None = None,
        content_key: str = "content",
    ) -> list[dict]:
        """
        Rerank documents using cross-encoder scores.

        The returned documents contain:
            `cross_encoder_score`

        Existing document order is not mutated.
        """

        if not documents:
            return []

        target_top_n = top_n if top_n is not None else self.top_n

        if target_top_n <= 0:
            return []

        model = self._get_model()

        scored_documents = [dict(document) for document in documents]

        pairs, truncated_count = self._build_pairs(
            query=query,
            documents=scored_documents,
            content_key=content_key,
        )

        if truncated_count:
            logger.debug(
                "{} of {} document chunk(s) " "truncated to {} characters",
                truncated_count,
                len(documents),
                self.max_content_chars,
            )

        logger.info(
            "Cross-encoder scoring {} pair(s)...",
            len(pairs),
        )

        scores = model.predict(pairs)

        self._attach_scores(
            documents=scored_documents,
            scores=scores,
        )

        scored_documents.sort(
            key=lambda document: document.get(
                "cross_encoder_score",
                0.0,
            ),
            reverse=True,
        )

        reranked = scored_documents[:target_top_n]

        self._log_result_summary(
            total_count=len(documents),
            reranked_count=len(reranked),
            documents=reranked,
        )

        return reranked

    def _build_pairs(
        self,
        query: str,
        documents: list[dict],
        content_key: str,
    ) -> tuple[list[list[str]], int]:
        """
        Build cross-encoder input pairs.

        Returns:
            (pairs, truncated_count)
        """

        pairs: list[list[str]] = []
        truncated_count = 0

        for document in documents:
            content = self._document_text(document, content_key)
            document["rerank_original_chars"] = len(content)
            document["rerank_truncated"] = len(content) > self.max_content_chars
            document["rerank_evidence_source"] = (
                "matched_children"
                if document.get("matched_child_documents")
                else "parent"
            )

            document["rerank_window_start"] = 0
            if len(content) > self.max_content_chars:
                content, window_start = self._select_relevant_window(
                    query,
                    content,
                    self.max_content_chars,
                )
                document["rerank_window_start"] = window_start
                truncated_count += 1

            document["rerank_input_chars"] = len(content)

            pairs.append([query, content])

        return pairs, truncated_count

    @staticmethod
    def _select_relevant_window(
        query: str,
        content: str,
        max_chars: int,
    ) -> tuple[str, int]:
        """Select the most query-relevant character window from long evidence."""
        if len(content) <= max_chars:
            return content, 0

        terms = {
            term
            for term in query.casefold().split()
            if len(term.strip(".,?!:;()[]{}\"'")) >= 3
        }
        terms = {
            term.strip(".,?!:;()[]{}\"'")
            for term in terms
        }
        if not terms:
            return content[:max_chars], 0

        # Preserve a compact heading prefix when the best evidence occurs
        # later, then spend the remaining budget on the relevant window.
        prefix_budget = min(240, max_chars // 5)
        body_budget = max_chars - prefix_budget - 5
        stride = max(body_budget // 2, 1)
        candidates = list(range(0, max(len(content) - body_budget + 1, 1), stride))
        final_start = max(len(content) - body_budget, 0)
        if final_start not in candidates:
            candidates.append(final_start)

        def score(start: int) -> tuple[int, int, int]:
            window = content[start : start + body_budget].casefold()
            matched = [term for term in terms if term in window]
            return (
                len(matched),
                sum(window.count(term) for term in matched),
                -start,
            )

        best_start = max(candidates, key=score)
        if best_start == 0:
            return content[:max_chars], 0

        prefix = content[:prefix_budget].rstrip()
        window = content[best_start : best_start + body_budget].strip()
        return f"{prefix}\n…\n{window}"[:max_chars], best_start

    @staticmethod
    def _document_text(document: dict, content_key: str) -> str:
        """Build reranker input from the evidence that matched retrieval.

        Hybrid search scores child chunks. Reusing those exact snippets keeps
        the cross-encoder focused on the evidence that selected the parent,
        even when the relevant child occurs near the end of a long parent.
        """
        headings = list(
            dict.fromkeys(
                value
                for key in ("title", "section")
                if (value := str(document.get(key) or "").strip())
            )
        )
        matched_children = document.get("matched_child_documents") or []
        child_evidence = [
            CrossEncoderReranker._format_child_evidence(child)
            for child in matched_children
            if str(child.get("content") or "").strip()
        ]
        content = (
            "\n\n".join(child_evidence)
            if child_evidence
            else str(document.get(content_key) or "")
        )
        return "\n\n".join([*headings, content]) if headings else content

    @staticmethod
    def _format_child_evidence(child: dict) -> str:
        """Add compact provenance without repeating identical headings."""
        headings = list(
            dict.fromkeys(
                value
                for key in ("title", "section")
                if (value := str(child.get(key) or "").strip())
            )
        )
        content = str(child.get("content") or "").strip()
        return "\n".join([*headings, content]) if headings else content

    @staticmethod
    def _attach_scores(
        documents: list[dict],
        scores: Any,
    ) -> None:
        """Attach cross-encoder scores to documents."""

        for document, score in zip(
            documents,
            scores,
        ):
            document["cross_encoder_score"] = float(score)

    @staticmethod
    def _log_result_summary(
        total_count: int,
        reranked_count: int,
        documents: list[dict],
    ) -> None:
        """Log reranking summary."""

        if not documents:
            logger.info(
                "Reranking done: {} → 0 documents",
                total_count,
            )
            return

        top_score = documents[0].get(
            "cross_encoder_score",
            0.0,
        )

        bottom_score = documents[-1].get(
            "cross_encoder_score",
            0.0,
        )

        logger.info(
            "Reranking done: {} → {} documents | " "top={:.4f} | bottom={:.4f}",
            total_count,
            reranked_count,
            top_score,
            bottom_score,
        )
