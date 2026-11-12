"""Read-only preflight, not a chatbot accuracy or SUS evaluation.

No LLM, embedding, ingestion, migration, or remote database write is performed.
Only public configuration and aggregate academic-corpus metadata are reported.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
from pathlib import Path
import platform

import yaml

from config.settings import get_settings
from src.monitoring.pipeline_snapshot import PROJECT_ROOT, capture_pipeline_snapshot


def read_table(client, table: str, columns: str) -> list[dict]:
    rows = []
    for start in range(0, 100_000, 500):
        page = (
            client.table(table).select(columns)
            .order(columns.split(',')[0])
            .range(start, start + 499).execute().data or []
        )
        rows.extend(page)
        if len(page) < 500:
            return rows
    raise RuntimeError('Metadata limit exceeded')


def check_database(client, settings) -> dict:
    parents = read_table(client, settings.table_parent_chunks, 'parent_id,domain,child_ids')
    children = read_table(client, settings.table_child_chunks, 'id,parent_id,section,domain,pages,source,embedding_status')
    parent_ids = {row['parent_id'] for row in parents}
    child_ids = {row['id'] for row in children}
    refs = [row.get('parent_id') or row.get('section') for row in children]
    missing_embedding = client.table(settings.table_child_chunks).select('id', count='exact', head=True).is_('embedding', 'null').execute().count
    empty_content = client.table(settings.table_child_chunks).select('id', count='exact', head=True).is_('content', 'null').execute().count
    auxiliary = {}
    for table in (
        'request_metrics', 'rag_execution_traces', 'source_document_versions',
        'research_participants', 'research_turns',
    ):
        try:
            response = client.table(table).select('*', count='exact', head=True).execute()
            auxiliary[table] = {'readable': True}
            if table not in ('research_participants', 'research_turns'):
                auxiliary[table]['rows'] = response.count
        except Exception as exc:
            auxiliary[table] = {'readable': False, 'error_type': type(exc).__name__}
    return {
        'read_only': True,
        'parent_count': len(parents), 'child_count': len(children),
        'parents_by_domain': dict(Counter(row.get('domain') or 'UNKNOWN' for row in parents)),
        'children_by_domain': dict(Counter(row.get('domain') or 'UNKNOWN' for row in children)),
        'orphan_child_count': sum(ref not in parent_ids for ref in refs),
        'dangling_parent_child_ids': sum(cid not in child_ids for row in parents for cid in row.get('child_ids') or []),
        'children_missing_pages': sum(not row.get('pages') for row in children),
        'children_missing_source': sum(not row.get('source') for row in children),
        'embedding_status_counts': dict(Counter(row.get('embedding_status') or 'UNKNOWN' for row in children)),
        'missing_embedding_count': missing_embedding,
        'null_child_content_count': empty_content,
        'auxiliary_tables': auxiliary,
    }


def build_report(settings, client=None) -> dict:
    manifest_path = PROJECT_ROOT / settings.EVALUATION_DOCUMENT_MANIFEST
    manifest = yaml.safe_load(manifest_path.read_text(encoding='utf-8'))
    documents = []
    for item in manifest.get('documents', []):
        path = PROJECT_ROOT / item['path']
        documents.append({
            'slug': item['slug'], 'domain': item['domain'],
            'path': item['path'], 'exists': path.is_file(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        })
    dependencies = {}
    for name in ('fastapi', 'openai', 'langchain-openai', 'tiktoken', 'supabase', 'pydantic'):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    warnings = []
    if not settings.USE_DATABASE_SESSIONS:
        warnings.append('Session persistence disabled: verify the website test environment before evaluation.')
    if not settings.ENABLE_REQUEST_METRICS:
        warnings.append('Request metrics disabled: backend durations will not be persisted.')
    if not settings.EVALUATION_AGENT_ENABLED:
        warnings.append('Database execution traces disabled: enable the existing feature or prepare a separate trace archive before evaluation.')
    if not settings.ENABLE_RESEARCH_REVIEW:
        warnings.append('Research question review is disabled. Enable it before collecting participant conversations.')
    if not all(item['exists'] for item in documents):
        warnings.append('One or more original source PDFs are missing.')
    report = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'purpose': 'pre_evaluation_readiness', 'formal_evaluation': False,
        'python': platform.python_version(), 'dependencies': dependencies,
        'pipeline_snapshot': capture_pipeline_snapshot(settings),
        'operational_settings': {name: getattr(settings, name) for name in (
            'USE_DATABASE_SESSIONS', 'ENABLE_REQUEST_METRICS', 'EVALUATION_AGENT_ENABLED',
            'ENABLE_RESEARCH_REVIEW',
            'REQUEST_TIMEOUT', 'REQUEST_QUEUE_TIMEOUT', 'MAX_CONCURRENT_REQUESTS',
            'RATE_LIMIT_REQUESTS', 'TIMEZONE',
        )},
        'source_documents': documents, 'warnings': warnings,
        'database': {'checked': False},
    }
    if client is not None:
        report['database'] = {'checked': True, **check_database(client, settings)}
        auxiliary = report['database']['auxiliary_tables']
        if not all(auxiliary[table]['readable'] for table in ('research_participants', 'research_turns')):
            warnings.append('Research tables are unavailable. Check migration 2026110601 before enrolling participants.')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', action='store_true', help='Read academic-corpus metadata only; never modify remote records.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new path; existing evidence is not overwritten.')
    settings = get_settings()
    client = None
    if args.database:
        from supabase import create_client
        client = create_client(settings.supabase_url, settings.supabase_service_key)
    try:
        report = build_report(settings, client)
    except Exception as exc:
        # Service errors can contain request URLs. Do not print raw credentials
        # or exception strings into a shareable readiness report.
        parser.exit(1, f'Preflight failed: {type(exc).__name__}\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
