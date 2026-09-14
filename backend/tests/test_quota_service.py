"""
Unit tests for backend/src/services/quota_service.py.
"""

from unittest.mock import Mock, patch
from src.services.quota_service import (
    check_and_update_quota,
    get_quota_status,
    _get_current_date,
)


class TestQuotaService:

    def test_get_current_date_format(self):
        """Pastikan tanggal diformat YYYY-MM-DD dan sesuai timezone."""
        date_str = _get_current_date()
        assert len(date_str) == 10
        assert date_str[4] == "-" and date_str[7] == "-"
        # Bagian tahun, bulan, hari adalah digit
        parts = date_str.split("-")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    @patch("src.services.quota_service._get_supabase_client")
    def test_check_quota_allowed(self, mock_get_client):
        """RPC mengembalikan True -> user diizinkan dan kuota terpotong."""
        mock_client = Mock()
        mock_rpc = Mock()
        mock_rpc.execute.return_value = Mock(data=True)
        mock_client.rpc.return_value = mock_rpc
        mock_get_client.return_value = mock_client

        result = check_and_update_quota("mhs-01", daily_limit=50)
        assert result is True
        mock_client.rpc.assert_called_once()
        args = mock_client.rpc.call_args[0]
        params = mock_client.rpc.call_args[0][1]
        assert args[0] == "increment_quota_if_under_limit"
        assert params["p_user_id"] == "mhs-01"
        assert params["p_daily_limit"] == 50

    @patch("src.services.quota_service._get_supabase_client")
    def test_check_quota_reached_limit(self, mock_get_client):
        """RPC mengembalikan False -> kuota harian user telah habis."""
        mock_client = Mock()
        mock_rpc = Mock()
        mock_rpc.execute.return_value = Mock(data=False)
        mock_client.rpc.return_value = mock_rpc
        mock_get_client.return_value = mock_client

        result = check_and_update_quota("mhs-02", daily_limit=100)
        assert result is False

    @patch("src.services.quota_service._get_supabase_client")
    def test_check_quota_table_response_allowed(self, mock_get_client):
        """RPC TABLE format: [{"allowed": True, "current_count": 5}] -> True."""
        mock_client = Mock()
        mock_rpc = Mock()
        mock_rpc.execute.return_value = Mock(data=[{"allowed": True, "current_count": 5}])
        mock_client.rpc.return_value = mock_rpc
        mock_get_client.return_value = mock_client

        result = check_and_update_quota("mhs-table-01", daily_limit=50)
        assert result is True

    @patch("src.services.quota_service._get_supabase_client")
    def test_check_quota_table_response_denied(self, mock_get_client):
        """RPC TABLE format: [{"allowed": False, "current_count": 100}] -> False."""
        mock_client = Mock()
        mock_rpc = Mock()
        mock_rpc.execute.return_value = Mock(data=[{"allowed": False, "current_count": 100}])
        mock_client.rpc.return_value = mock_rpc
        mock_get_client.return_value = mock_client

        result = check_and_update_quota("mhs-table-02", daily_limit=100)
        assert result is False

    @patch("src.services.quota_service._get_supabase_client")
    def test_check_quota_unexpected_data_fails_open(self, mock_get_client):
        """RPC mengembalikan None atau bukan boolean -> fail-open (True)."""
        mock_client = Mock()
        mock_rpc = Mock()
        mock_rpc.execute.return_value = Mock(data=None)
        mock_client.rpc.return_value = mock_rpc
        mock_get_client.return_value = mock_client

        # RPC mengembalikan None (misal schema return berubah / RPC bug)
        result = check_and_update_quota("mhs-03")
        assert result is True

    @patch("src.services.quota_service._get_supabase_client")
    def test_check_quota_db_exception_fails_open(self, mock_get_client):
        """Database error / koneksi putus -> fail-open (True)."""
        mock_client = Mock()
        mock_client.rpc.side_effect = RuntimeError("Supabase connection timeout")
        mock_get_client.return_value = mock_client

        result = check_and_update_quota("mhs-04")
        assert result is True

    @patch("src.services.quota_service._get_supabase_client")
    def test_check_quota_uses_settings_default_when_limit_none(self, mock_get_client):
        """Telegram bot memanggil tanpa daily_limit -> memakai settings.RATE_LIMIT_REQUESTS."""
        mock_client = Mock()
        mock_rpc = Mock()
        mock_rpc.execute.return_value = Mock(data=True)
        mock_client.rpc.return_value = mock_rpc
        mock_get_client.return_value = mock_client

        result = check_and_update_quota("user_telegram_123")
        assert result is True
        params = mock_client.rpc.call_args[0][1]
        assert params["p_daily_limit"] == 100  # Default di settings

    @patch("src.services.quota_service._get_supabase_client")
    def test_get_quota_status_success(self, mock_get_client):
        """get_quota_status mengembalikan sisa kuota yang dihitung dari DB."""
        mock_client = Mock()
        mock_table = Mock()
        mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = Mock(
            data=[{"message_count": 25}]
        )
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        status = get_quota_status("mhs-05")
        assert status["user_id"] == "mhs-05"
        assert status["current_count"] == 25
        assert status["limit"] == 100
        assert status["remaining"] == 75

    @patch("src.services.quota_service._get_supabase_client")
    def test_get_quota_status_fallback_on_error(self, mock_get_client):
        """get_quota_status menangani database error tanpa crash."""
        mock_client = Mock()
        mock_client.table.side_effect = Exception("DB error")
        mock_get_client.return_value = mock_client

        status = get_quota_status("mhs-06")
        assert status["user_id"] == "mhs-06"
        assert status["current_count"] == 0
        assert status["remaining"] == 100
        assert "error" in status
