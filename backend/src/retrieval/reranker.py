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

            if len(content) > self.max_content_chars:
                content = content[: self.max_content_chars]
                truncated_count += 1

            document["rerank_input_chars"] = len(content)

            pairs.append([query, content])

        return pairs, truncated_count

    @staticmethod
    def _document_text(document: dict, content_key: str) -> str:
        """Include document headings while preserving the original content."""
        headings = list(
            dict.fromkeys(
                value
                for key in ("title", "section")
                if (value := str(document.get(key) or "").strip())
            )
        )
        content = str(document.get(content_key) or "")
        return "\n\n".join([*headings, content]) if headings else content

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
