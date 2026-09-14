from unittest.mock import Mock

from src.generation.intent_classifier.reformulator import RewriteMethod
from src.generation.memory import ConversationMemory
from src.retrieval.query_planner import build_query_plan


def test_simple_query_uses_normalized_query_without_rewriter():
    memory = ConversationMemory()
    rewrite = Mock()

    plan = build_query_plan("  berapa SKS untuk PI?  ", memory, rewrite)

    assert plan.original_query == "berapa SKS untuk PI?"
    assert plan.normalized_query == "berapa SKS untuk Penulisan Ilmiah?"
    assert plan.resolved_query == plan.normalized_query
    assert plan.search_queries == (plan.resolved_query,)
    assert plan.rerank_query == plan.original_query
    assert plan.rewrite_method is RewriteMethod.NONE
    rewrite.assert_not_called()


def test_contextual_query_is_rewritten_using_prior_memory():
    memory = ConversationMemory()
    memory.add_user_turn("Apa syarat seminar PI?")
    memory.add_assistant_turn("Syaratnya tercantum dalam panduan.")
    rewrite = Mock(
        return_value=(
            "tahapan setelah seminar Penulisan Ilmiah",
            RewriteMethod.LLM,
        )
    )

    plan = build_query_plan("kalau sudah selesai, lanjut apa?", memory, rewrite)

    assert plan.resolved_query == "tahapan setelah seminar Penulisan Ilmiah"
    assert plan.rewrite_method is RewriteMethod.LLM
    assert plan.cache_key == plan.resolved_query
    rewrite.assert_called_once_with(plan.normalized_query, memory)
