"""Reference labels must stay outside every replay pipeline call."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

from scripts import run_chatbot_replay as replay
from src.generation.intent_classifier.reformulator import RewriteMethod
from src.retrieval.query_planner import QueryPlan


def test_replay_discards_labels_and_only_remembers_new_answers(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    output = tmp_path / "output.json"
    baseline.write_text(json.dumps({
        "sessions": [
            {"name": "first", "interactions": [
                {"index": 1, "question": "Pertanyaan pertama?", "answer": "OLD_ANSWER_SECRET",
                 "expected_answer": "EXPECTED_SECRET", "human_status": "LABEL_SECRET"},
                {"index": 2, "question": "Lalu langkahnya?", "answer": "OLD_ANSWER_SECRET"},
            ]},
            {"name": "second", "interactions": [
                {"index": 1, "question": "Pertanyaan sesi baru?", "answer": "OLD_ANSWER_SECRET"},
            ]},
        ],
    }), encoding="utf-8")

    histories = []
    def plan(question, memory):
        histories.append([turn.content for turn in memory.turns])
        return QueryPlan(question, question, question, (question,), question, RewriteMethod.NONE)

    generator = Mock()
    generator.generate.side_effect = [
        {"answer": "NEW_ANSWER_1"}, {"answer": "NEW_ANSWER_2"}, {"answer": "NEW_ANSWER_3"},
    ]
    collector = Mock()
    collector.to_trace_row.return_value = {}
    collector.to_row.return_value = {}
    monkeypatch.setattr(replay, "new_collector", lambda **kwargs: collector)
    monkeypatch.setattr(replay, "clear_current", lambda: None)
    monkeypatch.setattr(replay, "pipeline_fingerprint", lambda: "source-version")
    monkeypatch.setattr(replay, "build_query_plan", plan)
    monkeypatch.setattr(replay, "run_retrieval", lambda *args: SimpleNamespace(parent_documents=[], num_docs=0))
    monkeypatch.setattr(replay, "get_rag_generator", lambda: generator)
    monkeypatch.setattr(replay.sys, "argv", [
        "replay", str(baseline), "--sessions", "1", "2", "--output", str(output),
    ])

    replay.main()

    assert histories == [[], ["Pertanyaan pertama?", "NEW_ANSWER_1"], []]
    captured = repr(generator.generate.call_args_list) + output.read_text(encoding="utf-8")
    for sentinel in ("OLD_ANSWER_SECRET", "EXPECTED_SECRET", "LABEL_SECRET"):
        assert sentinel not in captured
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["evaluation_purpose"] == "development_regression"
    assert report["independent_test"] is False
    assert report["pipeline_sha256"] == "source-version"


def test_question_only_input_is_supported(tmp_path):
    path = tmp_path / "questions.json"
    sessions = [{"name": "example", "interactions": [{"index": 1, "question": "Apa syaratnya?"}]}]
    path.write_text(json.dumps({"sessions": sessions}), encoding="utf-8")
    assert replay.load_question_sessions(path) == sessions
