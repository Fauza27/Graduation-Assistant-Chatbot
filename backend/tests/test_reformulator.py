"""
Tests for QueryReformulator and deterministic rewrite rules.
Prevents regressions such as NameError or missing variables during rule-based query reformulation.
"""

from unittest.mock import Mock

from src.generation.intent_classifier.reformulator import (
    QueryReformulator,
    RewriteMethod,
    normalize_query,
)
from src.generation.memory import ConversationMemory


class TestQueryReformulatorRules:
    """Test deterministic rule-based query rewrites."""

    def test_rewrite_with_rules_kkp_suffix_follow_up(self):
        """Test follow-up rewrite with suffix '-nya' when previous topic is KKP."""
        reformulator = QueryReformulator(llm=Mock())
        memory = ConversationMemory()
        memory.add_user_turn("Bisa jelaskan tentang KKP?")
        memory.add_assistant_turn("KKP adalah Kuliah Kerja Praktik...")

        # Follow-up with suffix "syaratnya"
        rewritten, method = reformulator.reformulate("syaratnya apa?", memory)

        assert method == RewriteMethod.RULE
        assert "syarat KKP" in rewritten

    def test_rewrite_with_rules_skripsi_prefix_follow_up(self):
        """Test follow-up rewrite with prefix 'kalau' when previous topic is Skripsi."""
        reformulator = QueryReformulator(llm=Mock())
        memory = ConversationMemory()
        memory.add_user_turn("Bagaimana alur pendaftaran skripsi?")
        memory.add_assistant_turn("Alur pendaftaran skripsi dimulai dari...")

        rewritten, method = reformulator.reformulate("kalau batas akhirnya kapan?", memory)

        assert method == RewriteMethod.RULE
        assert "terkait Skripsi" in rewritten

    def test_rewrite_with_rules_non_skripsi_suffix_follow_up(self):
        """Test follow-up rewrite when previous topic is Tugas Akhir Non Skripsi."""
        reformulator = QueryReformulator(llm=Mock())
        memory = ConversationMemory()
        memory.add_user_turn("Info tugas akhir non skripsi dong")
        memory.add_assistant_turn("Tugas akhir non skripsi memiliki 3 jalur...")

        rewritten, method = reformulator.reformulate("prosedurnya gimana?", memory)

        assert method == RewriteMethod.RULE
        assert "prosedur Tugas Akhir Non Skripsi" in rewritten

    def test_rewrite_with_rules_implicit_reference(self):
        """Test follow-up rewrite with implicit reference 'itu'."""
        reformulator = QueryReformulator(llm=Mock())
        memory = ConversationMemory()
        memory.add_user_turn("Saya ingin tahu tentang Penulisan Ilmiah.")
        memory.add_assistant_turn("Penulisan Ilmiah adalah...")

        rewritten, method = reformulator.reformulate("apa manfaat dari program itu?", memory)

        assert method == RewriteMethod.RULE
        assert "Penulisan Ilmiah" in rewritten
        assert "itu" not in rewritten.lower()

    def test_rewrite_skips_if_topic_already_in_message(self):
        """Test that deterministic rewrite is skipped if the topic is already mentioned."""
        reformulator = QueryReformulator(llm=Mock())

        # Message already has "KKP" explicitly
        res = reformulator._rewrite_with_rules(
            message="berapa biaya KKP sekarang?",
            last_topic="KKP",
        )
        assert res is None

    def test_rewrite_skripsi_topic_suppression_boundary(self):
        """When last_topic is Skripsi, query having 'skripsi' alone is suppressed, but 'non skripsi' is not matched as 'skripsi'."""
        reformulator = QueryReformulator(llm=Mock())

        # Topic already present -> return None (no rule rewrite needed)
        assert reformulator._rewrite_with_rules("bagaimana syarat skripsi?", "Skripsi") is None

        # Message contains "non skripsi" but not standalone "skripsi" -> topic_already_present is False
        res = reformulator._rewrite_with_rules("kalau non skripsi bagaimana?", "Skripsi")
        assert res is not None
        assert "terkait Skripsi" in res

    def test_rewrite_with_rules_direct_call_no_name_error(self):
        """Direct test to guarantee _rewrite_with_rules does not raise NameError for message_lower or topic_lower."""
        reformulator = QueryReformulator(llm=Mock())

        topics = ["KKP", "Skripsi", "Penulisan Ilmiah", "Tugas Akhir Non Skripsi"]
        queries = [
            "syaratnya apa?",
            "kalau batas akhirnya kapan?",
            "prosedurnya gimana?",
            "apa manfaat dari program itu?",
        ]

        for topic in topics:
            for query in queries:
                result = reformulator._rewrite_with_rules(query, topic)
                assert result is not None
                assert topic.lower() in result.lower()

    def test_empty_memory_returns_none_method(self):
        """Test reformulate with empty memory returns original query and NONE method."""
        reformulator = QueryReformulator(llm=Mock())
        memory = ConversationMemory()

        query = "apa itu KKP?"
        rewritten, method = reformulator.reformulate(query, memory)

        assert method == RewriteMethod.NONE
        assert "KKP" in rewritten

    def test_normalize_query_does_not_treat_bare_praktik_as_kkp(self):
        assert normalize_query("bagaimana praktik anti plagiarisme?") == (
            "bagaimana praktik anti plagiarisme?"
        )
        assert "KKP" in normalize_query("apa syarat praktik kerja lapangan?")

    def test_normalize_non_skripsi_spelling_variants(self):
        assert normalize_query("syarat non-skripsi") == (
            "syarat Tugas Akhir Non Skripsi"
        )
        assert normalize_query("alur nonskripsi") == (
            "alur Tugas Akhir Non Skripsi"
        )

    def test_rule_resolves_tersebut_and_detail_without_llm(self):
        llm = Mock()
        reformulator = QueryReformulator(llm=llm)
        memory = ConversationMemory()
        memory.add_user_turn("Apa syarat jalur wirausaha?")
        memory.add_assistant_turn("Jalur wirausaha merupakan Non Skripsi.")

        rewritten, method = reformulator.reformulate(
            "bagaimana proses tersebut?",
            memory,
        )
        assert method is RewriteMethod.RULE
        assert "Tugas Akhir Non Skripsi" in rewritten

        rewritten, method = reformulator.reformulate("jelaskan lagi", memory)
        assert method is RewriteMethod.RULE
        assert rewritten == "jelaskan lagi terkait Tugas Akhir Non Skripsi?"
        llm.invoke.assert_not_called()
