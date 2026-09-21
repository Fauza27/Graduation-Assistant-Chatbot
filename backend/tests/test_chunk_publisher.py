import json

from scripts.database.publish_lossless_pi_kkp_chunks import _publish


class _RpcResult:
    data = {"updated_children": 1}

    def execute(self):
        return self


class _RecordingClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return _RpcResult()


def test_publish_keeps_ids_and_numbers_parents_per_document():
    parents = [
        {
            "parent_id": "pi-parent-1",
            "domain": "PI",
            "child_ids": ["pi-child-1"],
        },
        {
            "parent_id": "pi-parent-2",
            "domain": "PI",
            "child_ids": ["pi-child-2"],
        },
        {
            "parent_id": "kkp-parent-1",
            "domain": "KKP",
            "child_ids": ["kkp-child-1"],
        },
    ]
    children = [
        {"id": child_id, "content": child_id}
        for child_id in ("pi-child-1", "pi-child-2", "kkp-child-1")
    ]
    embeddings = {child["id"]: [0.25, -0.5] for child in children}
    client = _RecordingClient()

    _publish(client, parents, children, embeddings)

    assert [call[0] for call in client.calls] == [
        "replace_knowledge_parent_chunks",
    ] * 3
    payloads = [call[1] for call in client.calls]
    assert [payload["p_parent"]["parent_id"] for payload in payloads] == [
        "pi-parent-1",
        "pi-parent-2",
        "kkp-parent-1",
    ]
    assert [payload["p_parent"]["sequence_no"] for payload in payloads] == [1, 2, 1]
    assert [payload["p_children"][0]["sequence_no"] for payload in payloads] == [
        1,
        1,
        1,
    ]
    assert json.loads(payloads[0]["p_children"][0]["embedding"]) == [0.25, -0.5]
