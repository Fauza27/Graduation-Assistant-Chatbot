from src.evaluation_agent.document_reader import OriginalDocumentReader
from src.evaluation_agent.models import (
    DocumentPage,
    DocumentSpec,
    EvaluationCase,
    EvidenceCandidateLLM,
    RegisteredDocument,
    ReviewStatus,
)
from src.evaluation_agent.runner import EvaluationRunner


class FakeRepository:
    pass


class FakeReader:
    def read_pages(self, path):
        return [
            DocumentPage(page_number=index, text=f"isi {index}")
            for index in range(1, 6)
        ]

    build_windows = staticmethod(OriginalDocumentReader.build_windows)


class RecordingModel:
    model_name = "test-model"

    def __init__(self):
        self.windows = []

    def scan_window(self, cases, window):
        self.windows.append(
            (window.page_start, window.page_end, [case.case_id for case in cases])
        )
        return [
            EvidenceCandidateLLM(
                case_id=cases[0].case_id,
                is_relevant=window.page_start == 3,
                page_start=3,
                page_end=3,
                evidence_text="bukti" if window.page_start == 3 else "",
                confidence=0.8,
            )
        ]


def test_discovery_reads_every_window_and_batches_cases(monkeypatch, tmp_path):
    model = RecordingModel()
    runner = EvaluationRunner(
        repository=FakeRepository(), model=model, reader=FakeReader()
    )
    monkeypatch.setattr(runner.settings, "EVALUATION_PAGE_WINDOW", 3)
    monkeypatch.setattr(runner.settings, "EVALUATION_QUESTION_BATCH_SIZE", 10)
    monkeypatch.setattr(runner.settings, "EVALUATION_MAX_EVIDENCE_PER_CASE", 5)
    document = RegisteredDocument(
        document_id="doc",
        version_id="version",
        spec=DocumentSpec(
            slug="guide",
            title="Guide",
            domain="KKP",
            version="1",
            path=tmp_path / "guide.pdf",
            chunk_source="Guide",
        ),
        checksum_sha256="abc",
        page_count=5,
    )
    cases = [
        EvaluationCase(
            case_id="case-1",
            question="Pertanyaan?",
            review_status=ReviewStatus.INCORRECT,
        )
    ]

    found = runner._discover_evidence(cases, [document])

    assert [(start, end) for start, end, _ in model.windows] == [(1, 3), (3, 5)]
    assert found["case-1"][0].evidence_text == "bukti"


def test_discovery_rejects_unknown_cases_and_clamps_page_numbers(monkeypatch, tmp_path):
    class UntrustedOutputModel(RecordingModel):
        def scan_window(self, cases, window):
            return [
                EvidenceCandidateLLM(
                    case_id=cases[0].case_id,
                    is_relevant=True,
                    page_start=999,
                    page_end=1000,
                    evidence_text="bukti yang sama",
                    confidence=0.8,
                ),
                EvidenceCandidateLLM(
                    case_id="case-rekaan",
                    is_relevant=True,
                    evidence_text="abaikan",
                    confidence=1,
                ),
            ]

    runner = EvaluationRunner(
        repository=FakeRepository(), model=UntrustedOutputModel(), reader=FakeReader()
    )
    monkeypatch.setattr(runner.settings, "EVALUATION_PAGE_WINDOW", 3)
    monkeypatch.setattr(runner.settings, "EVALUATION_QUESTION_BATCH_SIZE", 10)
    monkeypatch.setattr(runner.settings, "EVALUATION_MAX_EVIDENCE_PER_CASE", 5)
    document = RegisteredDocument(
        document_id="doc",
        version_id="version",
        spec=DocumentSpec(
            slug="guide",
            title="Guide",
            domain="KKP",
            version="1",
            path=tmp_path / "guide.pdf",
            chunk_source="Guide",
        ),
        checksum_sha256="abc",
        page_count=5,
    )
    cases = [
        EvaluationCase(
            case_id="case-1",
            question="Pertanyaan?",
            review_status=ReviewStatus.INCORRECT,
        )
    ]

    found = runner._discover_evidence(cases, [document])

    assert list(found) == ["case-1"]
    assert len(found["case-1"]) == 1
    assert found["case-1"][0].page_start == 3
    assert found["case-1"][0].page_end == 3
