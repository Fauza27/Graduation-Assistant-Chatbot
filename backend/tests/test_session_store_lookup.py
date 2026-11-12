"""
Unit tests for session_store.py _OwnerLookup and delete_session behaviors.
"""

from unittest.mock import Mock, patch
import pytest

from src.generation.memory import ConversationMemory
from src.monitoring.errors import SessionAccessError
from src.services.session_store import DatabaseSessionStore, _OwnerLookup


class TestSessionStoreLookup:

    def test_owner_lookup_dataclass(self):
        """Pastikan _OwnerLookup membedakan status keberadaan dan owner_id."""
        not_found = _OwnerLookup(found=False, owner_id=None)
        assert not_found.found is False
        assert not_found.owner_id is None

        found_no_owner = _OwnerLookup(found=True, owner_id=None)
        assert found_no_owner.found is True
        assert found_no_owner.owner_id is None

        found_with_owner = _OwnerLookup(found=True, owner_id="user_123")
        assert found_with_owner.found is True
        assert found_with_owner.owner_id == "user_123"

    @patch.object(DatabaseSessionStore, "_test_connection")
    @patch.object(DatabaseSessionStore, "_create_supabase_client")
    def test_delete_session_not_found_returns_false(self, mock_client, mock_conn):
        """Jika session tidak ditemukan (found=False), delete_session mengembalikan False tanpa DB delete."""
        store = DatabaseSessionStore()
        store._get_existing_owner = Mock(return_value=_OwnerLookup(found=False, owner_id=None))

        deleted = store.delete_session("non_existent_session", mahasiswa_id="user_1")
        assert deleted is False
        store._get_existing_owner.assert_called_once_with("non_existent_session")

    @patch.object(DatabaseSessionStore, "_test_connection")
    @patch.object(DatabaseSessionStore, "_create_supabase_client")
    def test_delete_session_ownerless_telegram_success(self, mock_client, mock_conn):
        """Jika session ada tapi ownerless (Telegram, owner_id=None), delete_session berhasil dijalankan."""
        mock_sb = Mock()
        mock_delete = Mock()
        mock_delete.execute.return_value = Mock(data=[{"session_id": "tg_session"}])
        mock_sb.table.return_value.delete.return_value.eq.return_value.is_.return_value = mock_delete
        mock_client.return_value = mock_sb

        store = DatabaseSessionStore()
        store._supabase = mock_sb
        store._get_existing_owner = Mock(return_value=_OwnerLookup(found=True, owner_id=None))

        deleted = store.delete_session("tg_session", mahasiswa_id=None)
        assert deleted is True
        mock_sb.table.return_value.delete.return_value.eq.return_value.is_.assert_called_once_with(
            "mahasiswa_id", "null"
        )

    @patch.object(DatabaseSessionStore, "_test_connection")
    @patch.object(DatabaseSessionStore, "_create_supabase_client")
    def test_delete_session_idor_raises_session_access_error(self, mock_client, mock_conn):
        """Jika user_B mencoba menghapus sesi milik user_A, raise SessionAccessError."""
        store = DatabaseSessionStore()
        store._get_existing_owner = Mock(return_value=_OwnerLookup(found=True, owner_id="user_A"))

        with pytest.raises(SessionAccessError):
            store.delete_session("user_a_session", mahasiswa_id="user_B")

    @patch.object(DatabaseSessionStore, "_test_connection")
    @patch.object(DatabaseSessionStore, "_create_supabase_client")
    def test_web_access_denied_for_existing_telegram_row_with_and_without_cache(
        self, mock_client, mock_conn
    ):
        store = DatabaseSessionStore()
        table = mock_client.return_value.table.return_value
        read = table.select.return_value.eq.return_value.single.return_value
        read.execute.return_value.data = {"mahasiswa_id": None}
        memory = ConversationMemory()

        for warm_cache in (False, True):
            if warm_cache:
                store._cache.put("123456789", memory)
            with pytest.raises(SessionAccessError):
                store.load_memory("123456789", mahasiswa_id="user_A")
            with pytest.raises(SessionAccessError):
                store.save_memory("123456789", memory, channel="website", mahasiswa_id="user_A")
            with pytest.raises(SessionAccessError):
                store.delete_session("123456789", mahasiswa_id="user_A")

        table.upsert.assert_not_called()
        table.update.assert_not_called()
        table.delete.assert_not_called()

    @patch.object(DatabaseSessionStore, "_test_connection")
    @patch.object(DatabaseSessionStore, "_create_supabase_client")
    def test_new_row_conflict_never_overwrites_another_owner(self, mock_client, mock_conn):
        store = DatabaseSessionStore()
        table = mock_client.return_value.table.return_value
        table.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None
        table.upsert.return_value.execute.return_value.data = []
        by_session = table.update.return_value.eq.return_value
        by_session.eq.return_value.execute.return_value.data = []
        memory = store.load_memory("new-web-session", mahasiswa_id="user_A")

        with pytest.raises(SessionAccessError):
            store.save_memory("new-web-session", memory, channel="website", mahasiswa_id="user_A")

        assert table.upsert.call_args.kwargs == {
            "on_conflict": "session_id",
            "ignore_duplicates": True,
        }
        by_session.eq.assert_called_once_with("mahasiswa_id", "user_A")
        assert store._cache.peek_entry("new-web-session") is None
