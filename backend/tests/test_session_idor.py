"""
Unit tests for IDOR protection in session management.
Tests verify_session_owner() across all 5 key access scenarios.
"""

import pytest
from src.monitoring.errors import SessionAccessError, ChatError
from src.services.session_strategy import InMemorySessionStrategy, verify_session_owner


class TestSessionIDORProtection:

    def test_session_access_error_inherits_chat_error(self):
        """Pastikan SessionAccessError mewarisi ChatError dengan error_source='security_idor'."""
        err = SessionAccessError("user_A", "user_B")
        assert isinstance(err, ChatError)
        assert err.error_source == "security_idor"

    def test_scenario_a_unauthenticated_request_to_owned_session(self):
        """
        Skenario A: Sesi memiliki owner ('user_A').
        Request masuk tanpa identitas (mahasiswa_id=None).
        -> HARUS raise SessionAccessError (mencegah IDOR anonim).
        """
        with pytest.raises(SessionAccessError) as exc_info:
            verify_session_owner(session_owner_id="user_A", requested_owner_id=None)

        assert exc_info.value.session_owner_id == "user_A"
        assert exc_info.value.requested_owner_id is None

    def test_scenario_b_cross_user_access(self):
        """
        Skenario B: Sesi dimiliki user_A.
        Request masuk dari user_B.
        -> HARUS raise SessionAccessError.
        """
        with pytest.raises(SessionAccessError) as exc_info:
            verify_session_owner(session_owner_id="user_A", requested_owner_id="user_B")

        assert exc_info.value.session_owner_id == "user_A"
        assert exc_info.value.requested_owner_id == "user_B"

    def test_scenario_c_ownerless_session_access(self):
        """
        Skenario C: Sesi tanpa owner (session_owner_id=None, misal Telegram).
        Request masuk tanpa identitas (requested_owner_id=None).
        -> HARUS lolos tanpa exception.
        """
        # Tidak melempar exception
        verify_session_owner(session_owner_id=None, requested_owner_id=None)

    def test_scenario_d_valid_owner_access(self):
        """
        Skenario D: Sesi dimiliki user_A.
        Request masuk dari user_A.
        -> HARUS lolos tanpa exception.
        """
        # Tidak melempar exception
        verify_session_owner(session_owner_id="user_A", requested_owner_id="user_A")

    def test_scenario_e_website_cannot_claim_telegram_session(self):
        with pytest.raises(SessionAccessError):
            verify_session_owner(session_owner_id=None, requested_owner_id="user_A")


def test_in_memory_telegram_session_survives_web_access_attempts():
    store = InMemorySessionStrategy(max_sessions=8, ttl_seconds=60)
    memory = store.load_memory("123456789")
    memory.add_user_turn("Pesan sintetis Telegram.")

    with pytest.raises(SessionAccessError):
        store.load_memory("123456789", mahasiswa_id="user_A")
    with pytest.raises(SessionAccessError):
        store.save_memory("123456789", memory, channel="website", mahasiswa_id="user_A")
    with pytest.raises(SessionAccessError):
        store.delete_session("123456789", mahasiswa_id="user_A")

    assert store.get_session_details_for_user("123456789", "user_A") is None
    assert store.load_memory("123456789") is memory


def test_website_cannot_reserve_new_telegram_id():
    store = InMemorySessionStrategy(max_sessions=8, ttl_seconds=60)
    with pytest.raises(SessionAccessError):
        store.load_memory("123456789", mahasiswa_id="user_A")
    assert store.load_memory("123456789").turn_count == 0
    assert store.load_memory("web-session", mahasiswa_id="user_A").turn_count == 0
