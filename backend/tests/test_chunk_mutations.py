"""Regression coverage for admin reads and transactional write boundaries."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from postgrest.exceptions import APIError

from src.admin import chunk_editor, chunk_mutations
from src.admin.auth import ResourceNotFoundError


def test_knowledge_tree_executes_each_query_once():
    parents = Mock()
    parents.select.return_value.order.return_value.order.return_value.order.return_value = parents
    parents.execute.return_value = SimpleNamespace(data=[])
    children = Mock()
    children.select.return_value.order.return_value = children
    # Actual PostgREST responses have data, but cannot execute another query.
    children.execute.return_value = SimpleNamespace(data=[])
    client = Mock()
    client.table.side_effect = [parents, children]

    result = chunk_editor.list_knowledge_tree(client)

    assert result["documents"] == []
    assert result["summary"]["total_children"] == 0
    parents.execute.assert_called_once()
    children.execute.assert_called_once()


def test_save_keeps_omitted_fields_and_sends_one_atomic_operation():
    client = Mock()
    client.rpc.return_value.execute.return_value.data = {"content_changed": True}
    result = chunk_mutations.save_chunk("child", "admin", client, content=" New text ")

    assert result["content_changed"] is True
    client.rpc.assert_called_once_with("save_knowledge_chunk", {
        "p_child_id": "child", "p_admin_id": "admin", "p_title": None,
        "p_pages": None, "p_content": "New text",
    })
    client.table.assert_not_called()


@pytest.mark.parametrize("code,expected", [
    ("P0002", ResourceNotFoundError),
    ("40001", chunk_mutations.ChunkConflictError),
    ("22023", ValueError),
    ("08006", APIError),
])
def test_rpc_errors_preserve_api_semantics(code, expected):
    client = Mock()
    client.rpc.return_value.execute.side_effect = APIError({
        "code": code, "message": "operation failed", "details": None, "hint": None,
    })
    with pytest.raises(expected):
        chunk_mutations.delete_chunk("child", client)


def test_successful_embedding_publishes_through_atomic_rpc(monkeypatch):
    embed = Mock(return_value=[0.1, 0.2])
    monkeypatch.setattr(chunk_mutations, "_create_chunk_embedding", embed)
    client = Mock()

    chunk_mutations.process_chunk_reembed("log", "child", "Latest draft", client)

    embed.assert_called_once_with("Latest draft")
    client.rpc.assert_called_once_with("complete_chunk_reembed", {
        "p_log_id": "log", "p_child_id": "child", "p_embedding": [0.1, 0.2],
    })
    client.table.assert_not_called()


def test_embedding_failure_does_not_publish_or_mask_original_error(monkeypatch):
    failure = RuntimeError("embedding unavailable")
    monkeypatch.setattr(chunk_mutations, "_create_chunk_embedding", Mock(side_effect=failure))
    client = Mock()
    client.rpc.return_value.execute.side_effect = RuntimeError("failure report unavailable")

    with pytest.raises(RuntimeError) as exc:
        chunk_mutations.process_chunk_reembed("log", "child", "New text", client)

    assert exc.value is failure
    client.rpc.assert_called_once_with("fail_chunk_reembed", {
        "p_log_id": "log", "p_child_id": "child", "p_error": "embedding unavailable",
    })


def test_parent_conflict_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(chunk_mutations, "_create_chunk_embedding", Mock(return_value=[0.1]))
    client = Mock()
    conflict = APIError({"code": "40001", "message": "Ambiguous parent content"})
    client.rpc.return_value.execute.side_effect = [conflict, SimpleNamespace(data=None)]

    with pytest.raises(chunk_mutations.ChunkConflictError):
        chunk_mutations.process_chunk_reembed("log", "child", "New text", client)

    assert [call.args[0] for call in client.rpc.call_args_list] == [
        "complete_chunk_reembed", "fail_chunk_reembed",
    ]


def test_delete_conflict_maps_to_http_409():
    from fastapi import HTTPException
    from src.api.admin import delete_chunk_endpoint

    client = Mock()
    client.rpc.return_value.execute.side_effect = APIError({
        "code": "40001", "message": "Reembedding in progress",
    })
    with pytest.raises(HTTPException) as exc:
        delete_chunk_endpoint("child", admin={"sub": "admin"}, supabase=client)
    assert exc.value.status_code == 409


def test_reembed_endpoint_schedules_reserved_content():
    from fastapi import BackgroundTasks
    from src.api.admin import trigger_reembed_chunk

    client = Mock()
    client.rpc.return_value.execute.return_value.data = {
        "log_id": "log", "parent_id": "parent", "old_content": "Original",
        "new_content": "Latest draft",
    }
    tasks = BackgroundTasks()
    response = trigger_reembed_chunk("child", tasks, admin={"sub": "admin"}, supabase=client)

    assert response.status == "processing"
    assert tasks.tasks[0].args == ("log", "child", "Latest draft", client)
    assert tasks.tasks[0].is_async is False
