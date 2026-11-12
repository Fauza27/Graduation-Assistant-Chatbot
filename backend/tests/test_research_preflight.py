import json
from types import SimpleNamespace

from pydantic import ValidationError
import pytest

from config.settings import Settings
from scripts.check_research_readiness import build_report, check_database


def test_local_preflight_reports_sources_without_secrets(mock_settings):
    report = build_report(mock_settings)
    assert report['formal_evaluation'] is False
    assert report['database']['checked'] is False
    assert len(report['source_documents']) == 4
    assert all(row['exists'] and len(row['sha256']) == 64 for row in report['source_documents'])
    encoded = json.dumps(report)
    assert mock_settings.open_api_key not in encoded
    assert mock_settings.supabase_service_key not in encoded
    assert mock_settings.supabase_url not in encoded
    assert report['warnings']


def test_research_capture_requires_request_metrics(mock_settings):
    config = mock_settings.model_dump()
    config.update(ENABLE_RESEARCH_REVIEW=True, ENABLE_REQUEST_METRICS=False)
    with pytest.raises(ValidationError, match='ENABLE_REQUEST_METRICS'):
        Settings(_env_file=None, **config)


def test_database_preflight_uses_only_metadata_reads(mock_settings):
    calls = []

    class Query:
        def __init__(self, table):
            self.table = table
            self.head = False

        def select(self, columns, **kwargs):
            calls.append((self.table, columns, kwargs))
            self.head = kwargs.get('head', False)
            return self

        def range(self, start, end):
            return self

        def order(self, column):
            return self

        def is_(self, column, value):
            return self

        def execute(self):
            if self.head:
                return SimpleNamespace(count=0, data=[])
            if self.table == mock_settings.table_parent_chunks:
                return SimpleNamespace(data=[{'parent_id': 'p1', 'domain': 'PI', 'child_ids': ['c1', 'missing']}])
            return SimpleNamespace(data=[{'id': 'c1', 'parent_id': 'p1', 'domain': 'PI', 'pages': [7], 'source': 'PI', 'embedding_status': 'completed'}, {'id': 'c2', 'parent_id': 'missing', 'domain': 'KKP', 'pages': [], 'source': ''}])

    client = SimpleNamespace(table=Query)
    result = check_database(client, mock_settings)
    assert result['read_only'] is True
    assert result['orphan_child_count'] == 1
    assert result['dangling_parent_child_ids'] == 1
    assert result['children_missing_pages'] == 1
    assert all(
        not (set(columns.split(',')) & {'content', 'embedding'})
        for _, columns, _ in calls if columns != '*'
    )
