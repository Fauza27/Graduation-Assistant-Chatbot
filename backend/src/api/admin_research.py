"""Admin review of consented website conversations."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field

from config.settings import get_settings
from src.admin.auth import get_current_admin
from src.api.admin_metrics import _get_supabase_client

WITA = timezone(timedelta(hours=8))
PAGE_SIZE = 50
CODE_PATTERN = r"^P-[0-9]{1,6}$"
TURN_FIELDS = (
    "id,request_id,occurred_at,session_code,status,http_status,error_source,total_ms,disposition"
)
REVIEW_FIELDS = f"{TURN_FIELDS},question,answer,sources,reviewed_question,reviewed_answer"
EXPORT_FIELDS = f"{TURN_FIELDS},question:reviewed_question,answer:reviewed_answer,sources"


def require_review_enabled(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    if not get_settings().ENABLE_RESEARCH_REVIEW:
        raise HTTPException(503, "Penelaahan belum diaktifkan pada server ini.")


router = APIRouter(
    prefix="/admin/research",
    tags=["Admin Research Review"],
    dependencies=[Depends(get_current_admin), Depends(require_review_enabled)],
)


class Enrollment(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(pattern=CODE_PATTERN)
    confirmed: Literal[True]


class TurnReview(BaseModel):
    disposition: Literal["pending", "study", "practice", "test"]
    reviewed_question: str | None = Field(default=None, max_length=500)
    reviewed_answer: str | None = Field(default=None, max_length=30000)


@router.get("/participants")
def get_participants():
    return {
        "data": _get_supabase_client().table("research_participants")
        .select("code,consented_at").order("code").execute().data
    }


@router.post("/participants", status_code=201)
def enroll_participant(body: Enrollment):
    db = _get_supabase_client()
    accounts = db.table("mahasiswa_accounts").select("mahasiswa_id").eq(
        "email", body.email.strip()
    ).limit(2).execute().data
    if not accounts:
        raise HTTPException(404, "Akun tidak ditemukan. Peserta perlu login dengan email tersebut dahulu.")
    if len(accounts) != 1:
        raise HTTPException(409, "Email terkait dengan lebih dari satu akun.")
    try:
        participant = db.table("research_participants").insert({
            "mahasiswa_id": accounts[0]["mahasiswa_id"],
            "code": body.code,
        }).execute().data[0]
    except APIError as exc:
        if exc.code == "23505":
            raise HTTPException(409, "Kode atau akun peserta sudah terdaftar.") from exc
        raise
    return {"data": {"code": participant["code"], "consented_at": participant["consented_at"]}}


@router.delete("/participants/{code}")
def withdraw_participant(code: str):
    _get_supabase_client().table("research_participants").delete().eq("code", code).execute()
    return {"ok": True}


def period_page(start: date, end: date, code: str | None, before: int | None, export: bool):
    if end < start or end == date.max:
        raise HTTPException(422, "Periksa urutan tanggal mulai dan selesai.")
    fields = EXPORT_FIELDS if export else REVIEW_FIELDS
    query = _get_supabase_client().table("research_turns").select(
        f"{fields},research_participants!inner(code)"
    ).gte(
        "occurred_at", datetime.combine(start, time.min, WITA).isoformat()
    ).lt(
        "occurred_at", datetime.combine(end + timedelta(days=1), time.min, WITA).isoformat()
    )
    if code:
        query = query.eq("research_participants.code", code)
    if export:
        query = query.eq("disposition", "study")
    if before:
        query = query.lt("id", before)
    rows = query.order("id", desc=True).limit(PAGE_SIZE + 1).execute().data
    data = []
    for row in rows[:PAGE_SIZE]:
        participant = row.pop("research_participants")
        data.append({**row, "participant_code": participant["code"]})
    return {"data": data, "next_before": data[-1]["id"] if len(rows) > PAGE_SIZE else None}


@router.get("/turns")
def list_turns(
    start: date, end: date, code: str | None = Query(None, pattern=CODE_PATTERN),
    before: int | None = Query(None, gt=0),
):
    return period_page(start, end, code, before, export=False)


@router.get("/export")
def export_turns(
    start: date, end: date, code: str | None = Query(None, pattern=CODE_PATTERN),
    before: int | None = Query(None, gt=0),
):
    return period_page(start, end, code, before, export=True)


@router.get("/turns/{request_id}/context")
def get_context(request_id: UUID, before: int | None = Query(None, gt=0)):
    db = _get_supabase_client()
    selected = db.table("research_turns").select(
        "id,participant_id,session_code"
    ).eq("request_id", str(request_id)).limit(1).execute().data
    if not selected:
        raise HTTPException(404, "Rekaman tidak ditemukan.")
    target = selected[0]
    rows = db.table("research_turns").select(
        "id,request_id,occurred_at,question,answer,disposition"
    ).eq("participant_id", target["participant_id"]).eq(
        "session_code", target["session_code"]
    ).lt("id", min(target["id"], before or target["id"])).order(
        "id", desc=True
    ).limit(PAGE_SIZE + 1).execute().data
    data = rows[:PAGE_SIZE]
    return {"data": data, "next_before": data[-1]["id"] if len(rows) > PAGE_SIZE else None}


@router.patch("/turns/{request_id}")
def review_turn(request_id: UUID, review: TurnReview):
    db = _get_supabase_client()
    row = db.table("research_turns").select("answer").eq(
        "request_id", str(request_id)
    ).limit(1).execute().data
    if not row:
        raise HTTPException(404, "Rekaman tidak ditemukan.")
    question = (review.reviewed_question or "").strip()
    answer = (review.reviewed_answer or "").strip() if row[0]["answer"] is not None else None
    if review.disposition == "study":
        if not question or answer == "":
            raise HTTPException(422, "Isi salinan yang sudah diperiksa sebelum memasukkan pesan ke ekspor.")
    else:
        question = None
        answer = None
    result = db.table("research_turns").update({
        "disposition": review.disposition,
        "reviewed_question": question,
        "reviewed_answer": answer,
    }).eq("request_id", str(request_id)).execute().data
    if not result:
        raise HTTPException(404, "Rekaman tidak ditemukan.")
    return {"data": {
        "disposition": review.disposition,
        "reviewed_question": question,
        "reviewed_answer": answer,
    }}
