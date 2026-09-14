"""
Tests for AI services (Retrieval-First Architecture).
"""

import pytest
from unittest.mock import Mock, patch

from src.services.ai_services import (
    chat,
    get_or_create_memory,
    clear_session,
    get_session_stats,
    cleanup_sessions,
    preload_models,
)
from src.generation.memory import ConversationMemory
from src.retrieval.pipeline import RetrievalResult


class TestAIServices:

    def test_get_or_create_memory_new_session(self):
        """Test creating new memory for new session."""
        session_id = "test_session_1"
        memory = get_or_create_memory(session_id)

        assert isinstance(memory, ConversationMemory)
        assert memory.max_history_tokens == 2500
        assert len(memory.turns) == 0

    def test_get_or_create_memory_existing_session(self):
        """Test getting existing memory."""
        session_id = "test_session_2"

        # Create first time
        memory1 = get_or_create_memory(session_id)
        memory1.add_user_turn("Test question")

        # Get second time - should retrieve the updated memory
        memory2 = get_or_create_memory(session_id)

        assert len(memory2.turns) == 1
        assert memory2.turns[0].content == "Test question"

    def test_clear_session_existing(self):
        """Test clearing existing session."""
        session_id = "test_session_3"

        memory = get_or_create_memory(session_id)
        from src.services.ai_services import _save_memory_if_needed
        _save_memory_if_needed(session_id, memory)

        result = clear_session(session_id)
        assert isinstance(result, bool)

        new_memory = get_or_create_memory(session_id)
        assert len(new_memory.turns) == 0

    def test_clear_session_nonexistent(self):
        """Test clearing non-existent session."""
        result = clear_session("nonexistent_session_xyz")
        assert result is False

    def test_get_session_stats(self):
        """Test getting session statistics."""
        stats = get_session_stats()
        assert "storage_type" in stats
        assert any(k.startswith("active_sessions") for k in stats)

    def test_chat_empty_query(self):
        """Test chat with empty query."""
        result = chat("", "test_session", username="testuser")

        assert result["answer"] == "Pertanyaan tidak boleh kosong."
        assert result["num_docs"] == 0
        assert result["error"] == "empty_query"

    def test_chat_missing_session_id(self):
        """Test chat with missing session ID."""
        result = chat("Test question", "", username="testuser")

        assert result["answer"] == "Session ID diperlukan."
        assert result["num_docs"] == 0
        assert result["error"] == "missing_session_id"

    @patch("src.services.ai_services.get_rag_generator")
    @patch("src.retrieval.pipeline.run_retrieval")
    def test_chat_rag_flow(self, mock_run_retrieval, mock_get_rag_generator):
        """Test standard RAG chat flow."""
        mock_retrieval_result = RetrievalResult(
            parent_documents=[
                {
                    "parent_id": "parent-1",
                    "title": "Panduan KKP",
                    "section": "BAB II",
                    "content": "Syarat KKP adalah lulus 100 SKS.",
                    "cross_encoder_score": 0.85,
                    "matched_pages": [10, 11],
                }
            ],
            is_empty=False,
        )
        mock_run_retrieval.return_value = mock_retrieval_result

        mock_generator = Mock()
        mock_generator.generate.return_value = {
            "answer": "Syarat KKP adalah minimal 100 SKS.",
            "prompt_tokens": 100,
            "completion_tokens": 20,
        }
        mock_get_rag_generator.return_value = mock_generator

        result = chat(
            query="apa syarat kkp?",
            session_id="test_session_rag",
            username="testuser",
        )

        assert result["answer"] == "Syarat KKP adalah minimal 100 SKS."
        assert result["num_docs"] == 1
        assert len(result["sources"]) == 1
        assert result["sources"][0]["title"] == "Panduan KKP"

    def test_chat_exception_handling(self):
        """Test chat exception handling on unexpected runtime error."""
        with patch("src.services.ai_services.normalize_query", side_effect=RuntimeError("Unexpected error")):
            result = chat("Test question", "test_session_err", username="testuser")

            assert "terjadi kesalahan" in result["answer"].lower()
            assert result["num_docs"] == 0
            assert result["error"] == "Unexpected error"
            assert result["error_type"] == "RuntimeError"


if __name__ == "__main__":
    pytest.main([__file__])
