"""Regression tests for the monitoring API response envelope."""

from unittest.mock import Mock

import pytest

from src.api import admin_metrics


VIEW_ENDPOINTS = (
    admin_metrics.get_latency_stats,
    admin_metrics.get_stage_breakdown,
    admin_metrics.get_error_stats,
    admin_metrics.get_error_breakdown,
    admin_metrics.get_openai_retry_stats,
    admin_metrics.get_retrieval_quality,
    admin_metrics.get_domain_stats,
    admin_metrics.get_cost_stats,
    admin_metrics.get_new_vs_returning,
    admin_metrics.get_turns_per_session,
    admin_metrics.get_followup_rate,
    admin_metrics.get_admin_activity,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", VIEW_ENDPOINTS)
async def test_view_endpoint_returns_a_flat_data_array(monkeypatch, endpoint):
    row = {"day": "2026-09-16", "total_requests": 1}
    monkeypatch.setattr(
        admin_metrics,
        "_select_view",
        Mock(
            return_value={
                "data": [row],
                "metadata": {
                    "date_filter_applied": True,
                    "filter_error": None,
                    "requested_days": 7,
                    "total_records": 1,
                },
            }
        ),
    )

    response = await endpoint(days=7, admin={"role": "admin"})

    assert response["data"] == [row]
    assert isinstance(response["data"], list)
    assert response["total_records"] == 1


@pytest.mark.asyncio
async def test_active_users_returns_a_flat_data_array(monkeypatch):
    monkeypatch.setattr(
        admin_metrics,
        "_select_view",
        Mock(
            return_value={
                "data": [{"day": "2026-09-16", "active_users": 2}],
                "metadata": {
                    "date_filter_applied": True,
                    "filter_error": None,
                    "requested_days": 7,
                    "total_records": 1,
                },
            }
        ),
    )

    response = await admin_metrics.get_active_users(
        granularity="daily",
        days=7,
        admin={"role": "admin"},
    )

    assert response["data"] == [{"day": "2026-09-16", "active_users": 2}]
