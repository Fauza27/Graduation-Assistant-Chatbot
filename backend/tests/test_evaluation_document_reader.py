from src.evaluation_agent.document_reader import OriginalDocumentReader
from src.evaluation_agent.models import DocumentPage


def test_page_windows_cover_entire_document_with_overlap():
    pages = [
        DocumentPage(page_number=index, text=f"page {index}") for index in range(1, 8)
    ]

    windows = OriginalDocumentReader.build_windows(
        pages,
        document_slug="guide",
        document_title="Guide",
        version_id="v1",
        window_size=3,
        overlap=1,
    )

    assert [(window.page_start, window.page_end) for window in windows] == [
        (1, 3),
        (3, 5),
        (5, 7),
    ]
    assert all(
        f"HALAMAN FISIK {page}" in "\n".join(w.text for w in windows)
        for page in range(1, 8)
    )
