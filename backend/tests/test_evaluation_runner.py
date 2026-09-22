from src.evaluation_agent.document_reader import OriginalDocumentReader
from src.evaluation_agent.models import (
    AnswerAssessment,
    DocumentPage,
    DocumentSpec,
    EvaluationCase,
    EvidenceCandidate,
    EvidenceVerification,
    InformationNeed,
    QuestionPlan,
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


def test_discovery_indexes_original_pages_without_calling_llm(monkeypatch, tmp_path):
    class EvidenceReader(FakeReader):
        def read_pages(self, path):
            return [
                DocumentPage(
                    page_number=index,
                    text=(
                        "Syarat KKP adalah minimal 100 SKS dan IPK 2,00."
                        if index == 3
                        else f"isi umum halaman {index}"
                    ),
                )
                for index in range(1, 6)
            ]

    runner = EvaluationRunner(
        repository=FakeRepository(), model=object(), reader=EvidenceReader()
    )
    monkeypatch.setattr(runner.settings, "EVALUATION_PAGE_WINDOW", 3)
    monkeypatch.setattr(runner.settings, "EVALUATION_CANDIDATE_WINDOWS_PER_CASE", 4)
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
            question="minimal SKS KKP berapa?",
            review_status=ReviewStatus.INCORRECT,
        )
    ]

    found = runner._discover_evidence(cases, [document])

    assert found["case-1"]
    assert "100 SKS" in found["case-1"][0].evidence_text
    assert found["case-1"][0].page_start <= 3 <= found["case-1"][0].page_end


def test_discovery_reads_only_documents_selected_by_question_plan(tmp_path):
    class CountingReader(FakeReader):
        def __init__(self):
            self.paths = []

        def read_pages(self, path):
            self.paths.append(path)
            return super().read_pages(path)

    reader = CountingReader()
    runner = EvaluationRunner(
        repository=FakeRepository(), model=object(), reader=reader
    )
    documents = [
        RegisteredDocument(
            document_id=domain.lower(),
            version_id=f"version-{domain.lower()}",
            spec=DocumentSpec(
                slug=domain.lower(),
                title=domain,
                domain=domain,
                version="1",
                path=tmp_path / f"{domain.lower()}.pdf",
                chunk_source=domain,
            ),
            checksum_sha256="abc",
            page_count=5,
        )
        for domain in ("PI", "KKP")
    ]
    case = EvaluationCase(
        case_id="pi-only",
        question="minimal SKS PI berapa?",
        review_status="unreviewed",
        question_plan=QuestionPlan(
            case_id="pi-only",
            resolved_question="Berapa minimal SKS untuk PI?",
            target_domains=["PI"],
            information_needs=[
                InformationNeed(
                    need_id="pi_sks",
                    description="Minimal SKS PI",
                    domains=["PI"],
                )
            ],
            confidence=0.95,
        ),
    )

    runner._discover_evidence([case], documents)

    assert reader.paths == [tmp_path / "pi.pdf"]


def test_related_scope_evidence_is_retained_without_claiming_direct_answer(tmp_path):
    class ScopeReader(FakeReader):
        def read_pages(self, path):
            pages = super().read_pages(path)
            pages[2].text = "Proposal minimal 40 halaman."
            return pages

    class ScopeModel:
        def verify_evidence(self, case, window, evidence_text):
            return EvidenceVerification(
                answers_question=False,
                answer_available=False,
                is_related_scope=True,
                scope_note="Aturan hanya berlaku untuk seminar proposal.",
                corrected_evidence_text=evidence_text,
                page_start=3,
                page_end=3,
                explanation="Bukti terkait, tetapi cakupannya lebih sempit.",
                confidence=0.9,
            )

    runner = EvaluationRunner(
        repository=FakeRepository(), model=ScopeModel(), reader=ScopeReader()
    )
    document = RegisteredDocument(
        document_id="doc",
        version_id="version",
        spec=DocumentSpec(
            slug="guide",
            title="Guide",
            domain="SKRIPSI",
            version="1",
            path=tmp_path / "guide.pdf",
            chunk_source="Guide",
        ),
        checksum_sha256="abc",
        page_count=5,
    )
    case = EvaluationCase(
        case_id="case-1",
        question="Berapa halaman naskah Skripsi?",
        review_status=ReviewStatus.UNREVIEWED,
        queue_reason="answer_abstention",
    )
    candidate = EvidenceCandidate(
        case_id="case-1",
        version_id="version",
        document_slug="guide",
        document_title="Guide",
        page_start=3,
        page_end=3,
        evidence_text="Proposal minimal 40 halaman.",
        explanation="",
        confidence=0.8,
    )

    assessment = runner._assess_evidence(case, [candidate], {"version": document})

    assert assessment.direct is None
    assert assessment.related_scope is not None
    assert not assessment.related_scope.is_verified
    assert (
        assessment.attempts[0]["verification"]["scope_note"]
        == "Aturan hanya berlaku untuk seminar proposal."
    )
    assert assessment.discovery_status == "related_scope_only"


def test_wrong_document_domain_is_rejected_before_llm_call(tmp_path):
    runner = EvaluationRunner(
        repository=FakeRepository(), model=object(), reader=FakeReader()
    )
    document = RegisteredDocument(
        document_id="d",
        version_id="v",
        spec=DocumentSpec(
            slug="kkp",
            title="KKP",
            domain="KKP",
            version="1",
            path=tmp_path / "kkp.pdf",
            chunk_source="KKP",
        ),
        checksum_sha256="abc",
        page_count=5,
    )
    case = EvaluationCase(
        case_id="pi",
        question="berapa SKS PI?",
        review_status="unreviewed",
        standalone_question="berapa SKS KKP?",
    )
    candidate = EvidenceCandidate(
        case_id="pi",
        version_id="v",
        document_slug="kkp",
        document_title="KKP",
        page_start=3,
        page_end=3,
        evidence_text="100 SKS",
        explanation="",
        confidence=0.9,
    )
    result = runner._assess_evidence(case, [candidate], {"v": document})
    assert result.direct is None
    assert result.attempts[0]["rejection"] == "document_domain_mismatch"


def test_unverified_cases_never_call_diagnostic_llm_or_suggest_edits(monkeypatch):
    class Repository:
        def clear_case_results(self, *args):
            pass

        def update_run_case(self, *args, **kwargs):
            pass

        def update_run(self, *args, **kwargs):
            pass

        def load_trace(self, *args):
            return {}

        def save_finding(self, *args, **kwargs):
            pass

    runner = EvaluationRunner(
        repository=Repository(), model=object(), reader=FakeReader()
    )
    monkeypatch.setattr(
        "src.evaluation_agent.runner.build_system_context", lambda *args: {}
    )
    case = EvaluationCase(
        case_id="unrelated",
        question="layanan penitipan hewan KKP?",
        review_status="unreviewed",
    )
    results, failed = runner._diagnose_cases("run", [case], [], {})
    assert failed == 0
    assert results[0]["diagnosis"]["recommendations"] == []
    assert results[0]["diagnosis"]["failed_stage"] == "ambiguous"
    assert results[0]["evidence_search"]["status"] == "inconclusive"


def test_correct_answer_is_not_diagnosed_as_pipeline_failure(monkeypatch, tmp_path):
    from src.evaluation_agent.runner import EvidenceAssessment

    class Repository:
        def clear_case_results(self, *args):
            pass

        def update_run_case(self, *args, **kwargs):
            pass

        def update_run(self, *args, **kwargs):
            pass

        def load_trace(self, *args):
            return {}

        def load_chunks(self, *args):
            return [{"id": "c", "parent_id": "p", "content": "minimal 100 SKS"}]

        def load_parents(self, *args):
            return []

        def save_evidence(self, *args):
            pass

        def save_finding(self, *args, **kwargs):
            pass

    class Model:
        def assess_answer(self, *args):
            return AnswerAssessment(
                verdict="correct", explanation="Jawaban 100 SKS sesuai bukti."
            )

    case = EvaluationCase(
        case_id="correct",
        question="PI minimal SKS?",
        actual_answer="100 SKS",
        review_status="unreviewed",
    )
    document = RegisteredDocument(
        document_id="d",
        version_id="v",
        spec=DocumentSpec(
            slug="pi",
            title="PI",
            domain="PI",
            version="1",
            path=tmp_path / "pi.pdf",
            chunk_source="PI",
        ),
        checksum_sha256="abc",
        page_count=1,
    )
    evidence = EvidenceCandidate(
        case_id="correct",
        version_id="v",
        document_slug="pi",
        document_title="PI",
        page_start=1,
        page_end=1,
        evidence_text="minimal 100 SKS",
        explanation="Sesuai sumber",
        confidence=0.9,
        is_verified=True,
    )
    runner = EvaluationRunner(
        repository=Repository(), model=Model(), reader=FakeReader()
    )
    monkeypatch.setattr(
        runner, "_assess_evidence", lambda *args: EvidenceAssessment(direct=evidence)
    )
    monkeypatch.setattr(
        "src.evaluation_agent.runner.build_system_context", lambda *args: {}
    )
    results, failed = runner._diagnose_cases("run", [case], [document], {})
    assert failed == 0
    assert results[0]["answer_assessment"]["verdict"] == "correct"
    assert results[0]["diagnosis"]["recommendations"] == []
    assert results[0]["diagnosis"]["failed_stage"] == "unknown"


def test_comparison_requires_evidence_from_each_planned_document(tmp_path):
    class Model:
        def verify_evidence(self, case, window, evidence_text):
            need_id = "pi_requirement" if window.document_slug == "pi" else "kkp_requirement"
            return EvidenceVerification(
                answers_question=True,
                answer_available=True,
                corrected_evidence_text="isi 3",
                page_start=3,
                page_end=3,
                explanation="Bukti sesuai dokumen.",
                confidence=0.9,
                reference_answer="Persyaratan ditemukan.",
                verdict="supported",
                covered_need_ids=[need_id],
            )

    documents = {}
    candidates = []
    for domain, slug in (("PI", "pi"), ("KKP", "kkp")):
        version = f"version-{slug}"
        documents[version] = RegisteredDocument(
            document_id=f"doc-{slug}",
            version_id=version,
            spec=DocumentSpec(
                slug=slug,
                title=domain,
                domain=domain,
                version="1",
                path=tmp_path / f"{slug}.pdf",
                chunk_source=domain,
            ),
            checksum_sha256="abc",
            page_count=5,
        )
        candidates.append(
            EvidenceCandidate(
                case_id="comparison",
                version_id=version,
                document_slug=slug,
                document_title=domain,
                page_start=3,
                page_end=3,
                evidence_text="isi 3",
                explanation="",
                confidence=0.8,
            )
        )
    case = EvaluationCase(
        case_id="comparison",
        question="Syarat PI dan KKP sama?",
        review_status="unreviewed",
        question_plan=QuestionPlan(
            case_id="comparison",
            resolved_question="Bandingkan persyaratan PI dan KKP.",
            target_domains=["PI", "KKP"],
            information_needs=[
                InformationNeed(
                    need_id="pi_requirement",
                    description="Persyaratan PI",
                    domains=["PI"],
                ),
                InformationNeed(
                    need_id="kkp_requirement",
                    description="Persyaratan KKP",
                    domains=["KKP"],
                ),
            ],
            question_type="comparison",
            confidence=0.95,
        ),
    )
    runner = EvaluationRunner(
        repository=FakeRepository(), model=Model(), reader=FakeReader()
    )

    result = runner._assess_evidence(case, candidates, documents)

    assert result.discovery_status == "verified"
    assert len(result.supporting) == 2
    assert set(result.covered_need_ids) == {"pi_requirement", "kkp_requirement"}


def test_semantic_unit_mismatch_cannot_be_verified(tmp_path):
    class Model:
        def verify_evidence(self, case, window, evidence_text):
            return EvidenceVerification(
                answers_question=True,
                answer_available=True,
                corrected_evidence_text="isi 3",
                page_start=3,
                page_end=3,
                explanation="Durasi total dianggap sebagai jam per hari.",
                confidence=0.9,
                reference_answer="Durasi ditemukan.",
                verdict="supported",
                covered_need_ids=["daily_hours"],
                unit_matches=False,
            )

    document = RegisteredDocument(
        document_id="doc",
        version_id="version",
        spec=DocumentSpec(
            slug="kkp",
            title="KKP",
            domain="KKP",
            version="1",
            path=tmp_path / "kkp.pdf",
            chunk_source="KKP",
        ),
        checksum_sha256="abc",
        page_count=5,
    )
    case = EvaluationCase(
        case_id="hours",
        question="sehari wajib delapan jam kerja?",
        review_status="unreviewed",
        question_plan=QuestionPlan(
            case_id="hours",
            resolved_question="Apakah KKP wajib delapan jam kerja per hari?",
            target_domains=["KKP"],
            information_needs=[
                InformationNeed(
                    need_id="daily_hours",
                    description="Jumlah jam kerja KKP per hari",
                    domains=["KKP"],
                )
            ],
            confidence=0.95,
        ),
    )
    candidate = EvidenceCandidate(
        case_id="hours",
        version_id="version",
        document_slug="kkp",
        document_title="KKP",
        page_start=3,
        page_end=3,
        evidence_text="isi 3",
        explanation="",
        confidence=0.8,
    )
    runner = EvaluationRunner(
        repository=FakeRepository(), model=Model(), reader=FakeReader()
    )

    result = runner._assess_evidence(case, [candidate], {"version": document})

    assert result.direct is None
    assert result.attempts[0]["rejection"] == "semantic_unit_mismatch"
