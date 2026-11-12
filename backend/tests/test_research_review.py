from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import admin_research
from src.monitoring.context import RequestMetricsCollector
from src.monitoring import writer


def make_client(monkeypatch, role="admin"):
    monkeypatch.setattr(
        "src.admin.auth.verify_access_token", lambda _: {"role": role}
    )
    monkeypatch.setattr(
        admin_research, "get_settings", lambda: SimpleNamespace(ENABLE_RESEARCH_REVIEW=True)
    )
    app = FastAPI()
    app.include_router(admin_research.router)
    return TestClient(app, headers={"Authorization": "Bearer test"})


def test_research_routes_require_admin(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(admin_research, "_get_supabase_client", lambda: db)
    client = make_client(monkeypatch, role="mahasiswa")
    assert client.get("/admin/research/participants").status_code == 403
    assert client.get("/admin/research/export?start=2026-11-01&end=2026-11-06").status_code == 403
    db.table.assert_not_called()


def test_export_filters_and_pages_only_reviewed_copies(monkeypatch):
    db = MagicMock()
    table = db.table.return_value
    query = table.select.return_value
    for method in ("gte", "lt", "eq", "order", "limit"):
        getattr(query, method).return_value = query
    query.execute.return_value.data = [
        {"id": index, "question": "Teks tersamar", "research_participants": {"code": "P-001"}}
        for index in range(100, 49, -1)
    ]
    monkeypatch.setattr(admin_research, "_get_supabase_client", lambda: db)
    client = make_client(monkeypatch)
    response = client.get("/admin/research/export?start=2026-11-01&end=2026-11-06&code=P-001&before=101")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    fields = table.select.call_args.args[0].split(",")
    assert "question:reviewed_question" in fields and "answer:reviewed_answer" in fields
    assert not {"question", "answer", "mahasiswa_id", "participant_id"} & set(fields)
    query.gte.assert_called_once_with("occurred_at", "2026-11-01T00:00:00+08:00")
    query.lt.assert_any_call("occurred_at", "2026-11-07T00:00:00+08:00")
    query.lt.assert_any_call("id", 101)
    query.eq.assert_any_call("research_participants.code", "P-001")
    query.eq.assert_any_call("disposition", "study")
    assert len(response.json()["data"]) == 50
    assert response.json()["next_before"] == 51
    assert response.json()["data"][0]["participant_code"] == "P-001"


def test_export_approval_requires_reviewed_answer_when_original_exists(monkeypatch):
    db = MagicMock()
    table = db.table.return_value
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"answer": "Jawaban asli"}
    ]
    monkeypatch.setattr(admin_research, "_get_supabase_client", lambda: db)
    client = make_client(monkeypatch)
    url = f"/admin/research/turns/{uuid4()}"
    denied = client.patch(url, json={"disposition": "study", "reviewed_question": "Pertanyaan"})
    assert denied.status_code == 422
    table.update.assert_not_called()
    table.update.return_value.eq.return_value.execute.return_value.data = [{"id": 1}]
    saved = client.patch(url, json={"disposition": "practice", "reviewed_question": "Tidak ikut"})
    assert saved.status_code == 200
    table.update.assert_called_once_with({
        "disposition": "practice", "reviewed_question": None, "reviewed_answer": None,
    })


def test_research_capture_uses_answer_and_sources_from_successful_request(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(writer, "_get_supabase_client", lambda: db)
    collector = RequestMetricsCollector(
        channel="website", mahasiswa_id=str(uuid4()), session_id="session",
        question="Bagaimana syaratnya?", answer="Lihat panduan.", http_status=200,
        response_sources=[{"title": "Panduan", "pages": [7]}],
    )
    writer.persist_research_turn(collector, 2100)
    name, data = db.rpc.call_args.args
    assert name == "record_research_turn"
    assert data["p_request"] == collector.request_id
    assert data["p_answer"] == collector.answer
    assert data["p_sources"] == collector.response_sources
    collector.status = "error"
    collector.http_status = 504
    writer.persist_research_turn(collector, 30000)
    assert db.rpc.call_args.args[1]["p_answer"] is None
    assert db.rpc.call_args.args[1]["p_sources"] == []
    collector.http_status = 403
    db.reset_mock()
    writer.persist_research_turn(collector, 100)
    db.rpc.assert_not_called()
