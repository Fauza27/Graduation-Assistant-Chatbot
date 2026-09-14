"""
Unit tests for session_store.py _OwnerLookup and delete_session behaviors.
"""

from unittest.mock import Mock, patch
import pytest

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
        mock_sb.table.return_value.delete.return_value.eq.return_value = mock_delete
        mock_client.return_value = mock_sb

        store = DatabaseSessionStore()
        store._supabase = mock_sb
        store._get_existing_owner = Mock(return_value=_OwnerLookup(found=True, owner_id=None))

        deleted = store.delete_session("tg_session", mahasiswa_id=None)
        assert deleted is True

    @patch.object(DatabaseSessionStore, "_test_connection")
    @patch.object(DatabaseSessionStore, "_create_supabase_client")
    def test_delete_session_idor_raises_session_access_error(self, mock_client, mock_conn):
        """Jika user_B mencoba menghapus sesi milik user_A, raise SessionAccessError."""
        store = DatabaseSessionStore()
        store._get_existing_owner = Mock(return_value=_OwnerLookup(found=True, owner_id="user_A"))

        with pytest.raises(SessionAccessError):
            store.delete_session("user_a_session", mahasiswa_id="user_B")
