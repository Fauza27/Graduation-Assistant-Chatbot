"""
Unit tests for backend/src/api/ai.py.
Covers validation, Unicode sanitization, error propagation, metrics persistence, and context cleanup.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException, Request

from src.api.ai import (
    sanitize_input,
    validate_session_id,
    ChatRequest,
    ChatResponse,
    chat_endpoint,
)
from src.monitoring.context import get_current, clear_current
from src.monitoring.errors import SessionAccessError


@pytest.fixture(autouse=True)
def reset_monitoring_context():
    """Ensure each test runs with a clean context."""
    clear_current()
    yield
    clear_current()


# ============================================================================
# 1. Tests for validate_session_id
# ============================================================================

class TestValidateSessionId:
    def test_valid_session_ids(self):
        assert validate_session_id("abc") is True
        assert validate_session_id("session-123_test") is True
        assert validate_session_id("user_abc-def-123456789") is True

    def test_empty_or_too_short(self):
        assert validate_session_id("") is False
        assert validate_session_id("ab") is False

    def test_too_long(self):
        assert validate_session_id("a" * 101) is False

    def test_trailing_newline_rejected(self):
        """Dugaan (1): Pastikan session_id dengan newline di akhir ditolak (\\Z)."""
        assert validate_session_id("abc-123\n") is False
        assert validate_session_id("abc-123\r\n") is False

    def test_invalid_characters(self):
        assert validate_session_id("abc 123") is False
        assert validate_session_id("abc$123") is False
        assert validate_session_id("abc/123") is False
        assert validate_session_id("abc;drop table") is False


# ============================================================================
# 2. Tests for sanitize_input
# ============================================================================

class TestSanitizeInput:
    def test_basic_sanitization(self):
        text = "  Halo,   apa kabar?  "
        assert sanitize_input(text) == "Halo, apa kabar?"

    def test_strip_cf_unicode_characters(self):
        """Dugaan (2): Pastikan karakter format Cf (RTL override, ZWSP, BOM) disaring."""
        # \\u202e = Right-to-Left Override
        # \\u200b = Zero-Width Space
        # \\ufeff = Byte Order Mark / Zero-Width No-Break Space
        text = "\u202eBuku\u200b Panduan\ufeff KKP"
        cleaned = sanitize_input(text)
        assert cleaned == "Buku Panduan KKP"
        assert "\u202e" not in cleaned
        assert "\u200b" not in cleaned
        assert "\ufeff" not in cleaned

    def test_strip_cc_unicode_control_characters(self):
        text = "Teks\x00dengan\x07kontrol"
        assert sanitize_input(text) == "Teksdengankontrol"

    def test_preserve_allowed_whitespace(self):
        text = "Baris satu\nBaris dua\tTabbed"
        assert sanitize_input(text) == "Baris satu\nBaris dua Tabbed"

    def test_clean_and_normalize_before_truncation(self):
        """Pastikan pembersihan dilakukan sebelum truncation."""
        # 10 karakter format di awal, diikuti 15 karakter teks bermakna
        text = ("\u200b" * 10) + "123456789012345"
        # Jika truncate dulu ke 15, lalu dibersihkan: hanya tersisa 5 karakter
        # Jika bersihkan dulu lalu truncate ke 15: tersisa 15 karakter
        result = sanitize_input(text, max_length=15)
        assert result == "123456789012345"

    def test_non_string_input(self):
        assert sanitize_input(None) == ""
        assert sanitize_input(123) == ""


# ============================================================================
# 3. Tests for ChatRequest & ChatResponse Models
# ============================================================================

class TestChatModels:
    def test_chat_request_valid(self):
        req = ChatRequest(query="Apa syarat KKP?", session_id="sess-01", channel="website")
        assert req.query == "Apa syarat KKP?"
        assert req.session_id == "sess-01"
        assert req.channel == "website"

    def test_chat_request_trailing_newline_session_fails(self):
        with pytest.raises(ValueError, match="Format Session ID tidak valid"):
            ChatRequest(query="Apa syarat KKP?", session_id="sess-01\n", channel="website")

    def test_chat_request_empty_query_fails(self):
        with pytest.raises(ValueError, match="Pertanyaan tidak boleh kosong"):
            ChatRequest(query="   ", session_id="sess-01")

    def test_chat_response_schema_with_error(self):
        resp = ChatResponse(
            answer="Maaf terjadi kesalahan",
            num_docs=0,
            session_id="sess-01",
            error="Connection timeout"
        )
        assert resp.error == "Connection timeout"
        assert resp.intent is None


# ============================================================================
# 4. Tests for chat_endpoint & Observability
# ============================================================================

class TestChatEndpoint:
    def _create_mock_request(self, auth_header: str | None = None) -> Request:
        mock_req = Mock(spec=Request)
        headers = {}
        if auth_header:
            headers["Authorization"] = auth_header
        mock_req.headers = headers
        return mock_req

    @pytest.mark.asyncio
    @patch("src.api.ai.persist_metrics")
    async def test_telegram_channel_rejection_persists_metrics_and_cleans_context(self, mock_persist):
        """Telegram channel harus melempar 403, mem-persist metrics, dan membersihkan context."""
        body = ChatRequest(query="Halo", session_id="sess-tg-1", channel="telegram")
        request = self._create_mock_request()

        with pytest.raises(HTTPException) as exc_info:
            await chat_endpoint(body, request)

        assert exc_info.value.status_code == 403
        assert mock_persist.called
        collector = mock_persist.call_args[0][0]
        assert collector.status == "error"
        assert collector.http_status == 403
        assert collector.error_source == "channel_restriction"
        # ContextVar harus bersih
        assert get_current() is None

    @pytest.mark.asyncio
    @patch("src.api.ai.persist_metrics")
    async def test_unauthenticated_website_persists_metrics(self, mock_persist):
        """Website request tanpa token harus 401 dan mem-persist metrics."""
        body = ChatRequest(query="Halo apa syarat kkp?", session_id="sess-web-1", channel="website")
        request = self._create_mock_request(auth_header=None)

        with pytest.raises(HTTPException) as exc_info:
            await chat_endpoint(body, request)

        assert exc_info.value.status_code == 401
        assert mock_persist.called
        collector = mock_persist.call_args[0][0]
        assert collector.status == "error"
        assert collector.http_status == 401
        assert collector.error_source == "authentication"
        assert get_current() is None

    @pytest.mark.asyncio
    @patch("src.api.ai.persist_metrics")
    @patch("src.api.ai.verify_access_token")
    async def test_invalid_role_persists_metrics(self, mock_verify, mock_persist):
        """Website user dengan role bukan 'mahasiswa' harus 403 dan mem-persist metrics."""
        mock_verify.return_value = {"role": "dosen", "sub": "123"}
        body = ChatRequest(query="Halo apa syarat kkp?", session_id="sess-web-2", channel="website")
        request = self._create_mock_request(auth_header="Bearer token123")

        with pytest.raises(HTTPException) as exc_info:
            await chat_endpoint(body, request)

        assert exc_info.value.status_code == 403
        assert mock_persist.called
        collector = mock_persist.call_args[0][0]
        assert collector.status == "error"
        assert collector.http_status == 403
        assert get_current() is None

    @pytest.mark.asyncio
    @patch("src.api.ai.persist_metrics")
    @patch("src.api.ai.chat_service")
    @patch("src.api.ai.verify_access_token")
    @patch("src.api.ai.check_and_update_quota", return_value=True)
    async def test_session_access_error_reaches_global_handler_with_403_metrics(
        self, mock_quota, mock_verify, mock_chat_service, mock_persist
    ):
        """Penolakan akses sesi tetap dapat ditangani handler global sebagai 403."""
        mock_verify.return_value = {"role": "mahasiswa", "sub": "other-user"}
        access_error = SessionAccessError("session-owner", "other-user")
        mock_chat_service.side_effect = access_error
        body = ChatRequest(query="Apa syarat KKP?", session_id="owned-session")
        request = self._create_mock_request(auth_header="Bearer valid_token")

        with pytest.raises(SessionAccessError) as exc_info:
            await chat_endpoint(body, request)

        assert exc_info.value is access_error
        mock_persist.assert_called_once()
        collector = mock_persist.call_args.args[0]
        assert collector.status == "error"
        assert collector.http_status == 403
        assert collector.error_source == "security_idor"
        assert collector.error_type == "SessionAccessError"
        assert get_current() is None

    @pytest.mark.asyncio
    @patch("src.api.ai.persist_quota_rejection")
    @patch("src.api.ai.verify_access_token")
    @patch("src.api.ai.check_and_update_quota")
    async def test_quota_rejection_persists_once(self, mock_quota, mock_verify, mock_persist_quota):
        """Jika kuota habis (429), persist_quota_rejection dipanggil dan HTTPException 429 dilempar."""
        mock_verify.return_value = {"role": "mahasiswa", "sub": "mhs-101", "name": "Budi"}
        mock_quota.return_value = False  # kuota habis

        body = ChatRequest(query="Pertanyaan ke-11", session_id="sess-quota", channel="website")
        request = self._create_mock_request(auth_header="Bearer valid_token")

        with pytest.raises(HTTPException) as exc_info:
            await chat_endpoint(body, request)

        assert exc_info.value.status_code == 429
        assert "mencapai batas kuota harian" in exc_info.value.detail
        assert mock_persist_quota.call_count == 1
        assert mock_persist_quota.call_args[1]["session_id"] == "sess-quota"
        assert mock_persist_quota.call_args[1]["channel"] == "website"
        assert mock_persist_quota.call_args[1]["mahasiswa_id"] == "mhs-101"
        assert get_current() is None

    def test_collector_idempotency_prevents_duplicate_persist(self):
        """Pastikan collector tidak di-insert dua kali ke tabel request_metrics."""
        from src.monitoring.context import new_collector
        from src.monitoring.writer import persist_metrics

        try:
            collector = new_collector(session_id="s1", channel="website")
            with (
                patch("src.monitoring.writer._get_supabase_client") as mock_client,
                patch("src.monitoring.writer._metrics_enabled", return_value=True),
            ):
                mock_table = Mock()
                mock_client.return_value.table.return_value = mock_table
                mock_table.insert.return_value.execute.return_value = None

                persist_metrics(collector)
                assert collector._persisted is True
                assert mock_table.insert.call_count == 1

                # Panggilan kedua harus no-op karena _persisted sudah True
                persist_metrics(collector)
                assert mock_table.insert.call_count == 1
        finally:
            clear_current()

    @pytest.mark.asyncio
    @patch("src.api.ai.chat_service")
    @patch("src.api.ai.verify_access_token")
    @patch("src.api.ai.check_and_update_quota")
    async def test_successful_chat_endpoint(self, mock_quota, mock_verify, mock_chat_service):
        """Jalur sukses mengembalikan ChatResponse dan membersihkan context."""
        mock_verify.return_value = {"role": "mahasiswa", "sub": "mhs-101", "name": "Budi"}
        mock_quota.return_value = True
        mock_chat_service.return_value = {
            "answer": "Syarat KKP adalah 100 SKS.",
            "num_docs": 1,
            "sources": [{"title": "Panduan KKP"}],
        }

        body = ChatRequest(query="Apa syarat KKP?", session_id="sess-success", channel="website")
        request = self._create_mock_request(auth_header="Bearer valid_token")

        response = await chat_endpoint(body, request)
        assert isinstance(response, ChatResponse)
        assert response.answer == "Syarat KKP adalah 100 SKS."
        assert response.num_docs == 1
        assert response.error is None
        assert get_current() is None

    @pytest.mark.asyncio
    @patch("src.api.ai.persist_metrics")
    @patch("src.api.ai.verify_access_token")
    async def test_unexpected_endpoint_error_persists_500(self, mock_verify, mock_persist):
        """Error tak terduga di endpoint harus dicatat sebagai 500 dan dilempar ke client."""
        mock_verify.side_effect = RuntimeError("Database down")
        body = ChatRequest(query="Pertanyaan error", session_id="sess-err-500", channel="website")
        request = self._create_mock_request(auth_header="Bearer valid_token")

        with pytest.raises(HTTPException) as exc_info:
            await chat_endpoint(body, request)

        assert exc_info.value.status_code == 500
        assert mock_persist.called
        collector = mock_persist.call_args[0][0]
        assert collector.status == "error"
        assert collector.http_status == 500
        assert collector.error_type == "RuntimeError"
        assert get_current() is None
