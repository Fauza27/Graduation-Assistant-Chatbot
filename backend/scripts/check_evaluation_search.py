"""Offline source-search benchmark. No database writes or model/API calls.

Run: python -m scripts.check_evaluation_search
This measures candidate page recall only, not semantic verification accuracy.
"""

from __future__ import annotations

import json

from src.evaluation_agent.document_reader import (
    PROJECT_ROOT,
    OriginalDocumentReader,
    load_document_manifest,
)
from src.evaluation_agent.evidence_search import OriginalDocumentIndex
from src.evaluation_agent.evidence_validation import normalize_quote
from src.evaluation_agent.models import ConversationTurn, EvaluationCase


def main() -> int:
    fixtures = json.loads(
        (PROJECT_ROOT / "tests/fixtures/evaluation_search_cases.json").read_text(
            encoding="utf-8"
        )
    )
    reader = OriginalDocumentReader()
    windows = []
    pages_by_domain = {}
    domains_by_slug = {}
    for spec in load_document_manifest("config/evaluation_documents.yaml"):
        pages = reader.read_pages(spec.path)
        pages_by_domain[spec.domain] = pages
        domains_by_slug[spec.slug] = spec.domain
        windows.extend(
            (window, spec.domain)
            for window in reader.build_windows(
                pages,
                document_slug=spec.slug,
                document_title=spec.title,
                version_id=spec.slug,
                window_size=3,
            )
        )
    index = OriginalDocumentIndex(windows)
    passed = 0
    for item in fixtures:
        case = EvaluationCase(
            case_id=item["id"],
            question=item["question"],
            review_status="unreviewed",
            standalone_question=item.get("recorded_query"),
            prior_questions=item["history"],
            conversation_context=[
                ConversationTurn(question=q) for q in item["history"][-3:]
            ],
        )
        source = pages_by_domain[item["domain"]][item["page"] - 1].text
        quote_valid = normalize_quote(item["quote"]) in normalize_quote(source)
        candidates = index.search(case, limit=8)
        found = any(
            domains_by_slug[row.window.document_slug] == item["domain"]
            and row.window.page_start <= item["page"] <= row.window.page_end
            for row in candidates
        )
        passed += int(quote_valid and found)
        print(
            f"{item['id']}: source_quote={quote_valid}, expected_page_in_top8={found}"
        )
    print(
        f"Offline candidate recall with valid source quotes: {passed}/{len(fixtures)}"
    )
    return 0 if passed == len(fixtures) else 1


if __name__ == "__main__":
    raise SystemExit(main())
