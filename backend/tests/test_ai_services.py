"""
Tests for AI services
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from src.services.ai_services import (
    chat, 
    get_or_create_memory, 
    clear_session, 
    get_session_stats,
    ChatError,
    RetrievalError
)
from src.generation.memory import ConversationMemory, IntentType


class TestAIServices:
    
    def test_get_or_create_memory_new_session(self):
        """Test creating new memory for new session"""
        session_id = "test_session_1"
        memory = get_or_create_memory(session_id)
        
        assert isinstance(memory, ConversationMemory)
        assert memory.max_turns == 5
        assert len(memory.turns) == 0
    
    def test_get_or_create_memory_existing_session(self):
        """Test getting existing memory"""
        session_id = "test_session_2"
        
        # Create first time
        memory1 = get_or_create_memory(session_id)
        memory1.add_user_turn("Test question")
        
        # Get second time - should be same instance
        memory2 = get_or_create_memory(session_id)
        
        assert memory1 is memory2
        assert len(memory2.turns) == 1
    
    def test_clear_session_existing(self):
        """Test clearing existing session"""
        session_id = "test_session_3"
        
        # Create session
        get_or_create_memory(session_id)
        
        # Clear it
        result = clear_session(session_id)
        assert result is True
        
        # Should create new memory now
        new_memory = get_or_create_memory(session_id)
        assert len(new_memory.turns) == 0
    
    def test_clear_session_nonexistent(self):
        """Test clearing non-existent session"""
        result = clear_session("nonexistent_session")
        assert result is False
    
    def test_get_session_stats(self):
        """Test getting session statistics"""
        # Clear any existing sessions
        from src.services.ai_services import _session_store
        _session_store.clear()
        
        # Create some sessions
        get_or_create_memory("session1").add_user_turn("Q1")
        get_or_create_memory("session2").add_user_turn("Q2")
        get_or_create_memory("session2").add_user_turn("Q3")
        
        stats = get_session_stats()
        
        assert stats["active_sessions"] == 2
        assert stats["total_turns"] == 3
        assert "session1" in stats["sessions"]
        assert "session2" in stats["sessions"]
    
    def test_chat_empty_query(self):
        """Test chat with empty query"""
        result = chat("", "test_session")
        
        assert result["answer"] == "Pertanyaan tidak boleh kosong."
        assert result["num_docs"] == 0
        assert result["error"] == "empty_query"
    
    def test_chat_missing_session_id(self):
        """Test chat with missing session ID"""
        result = chat("Test question", "")
        
        assert result["answer"] == "Session ID diperlukan."
        assert result["num_docs"] == 0
        assert result["error"] == "missing_session_id"
    
    @patch('src.services.ai_services._classifier')
    @patch('src.services.ai_services._rag_chain')
    def test_chat_conversational_intent(self, mock_rag_chain, mock_classifier):
        """Test chat with conversational intent"""
        # Setup mocks
        mock_classifier.classify.return_value = (IntentType.CONVERSATIONAL, 0.9, "greeting")
        mock_rag_chain.invoke_conversational.return_value = {"answer": "Halo! Ada yang bisa saya bantu?"}
        
        result = chat("Halo", "test_session")
        
        assert result["answer"] == "Halo! Ada yang bisa saya bantu?"
        assert result["num_docs"] == 0
        assert result["intent"] == "conversational"
        assert result["confidence"] == 0.9
    
    @patch('src.services.ai_services._classifier')
    @patch('src.services.ai_services._rag_chain')
    def test_chat_clarification_intent(self, mock_rag_chain, mock_classifier):
        """Test chat with clarification intent"""
        # Setup mocks
        mock_classifier.classify.return_value = (IntentType.CLARIFICATION, 0.8, "follow_up")
        mock_rag_chain.invoke_clarification.return_value = {"answer": "Maksud Anda adalah..."}
        
        result = chat("Bisa dijelaskan lebih detail?", "test_session")
        
        assert result["answer"] == "Maksud Anda adalah..."
        assert result["num_docs"] == 0
        assert result["intent"] == "clarification"
        assert result["confidence"] == 0.8
    
    @patch('src.services.ai_services._classifier')
    @patch('src.services.ai_services._handle_retrieval')
    def test_chat_needs_retrieval_intent(self, mock_handle_retrieval, mock_classifier):
        """Test chat with needs retrieval intent"""
        # Setup mocks
        mock_classifier.classify.return_value = (IntentType.NEEDS_RETRIEVAL, 0.95, "academic_question")
        mock_handle_retrieval.return_value = {
            "answer": "Syarat PI adalah minimal 120 SKS",
            "num_docs": 2,
            "sources": []
        }
        
        result = chat("Apa syarat PI?", "test_session")
        
        assert result["answer"] == "Syarat PI adalah minimal 120 SKS"
        assert result["num_docs"] == 2
        mock_handle_retrieval.assert_called_once()
    
    @patch('src.services.ai_services._classifier')
    def test_chat_exception_handling(self, mock_classifier):
        """Test chat exception handling"""
        # Setup mock to raise exception
        mock_classifier.classify.side_effect = Exception("Test error")
        
        result = chat("Test question", "test_session")
        
        assert "terjadi kesalahan" in result["answer"].lower()
        assert result["num_docs"] == 0
        assert result["error"] == "Test error"
        assert result["error_type"] == "Exception"


class TestRetrievalHandling:
    
    @patch('src.services.ai_services.extract_query_components')
    @patch('src.services.ai_services.HybridSearcher')
    def test_handle_retrieval_no_results(self, mock_searcher_class, mock_extract):
        """Test retrieval when no search results found"""
        from src.services.ai_services import _handle_retrieval
        from src.generation.memory import ConversationMemory
        
        # Setup mocks
        mock_extract.return_value = Mock(semantic_query="test", filters={})
        mock_searcher = Mock()
        mock_searcher.search.return_value = []
        mock_searcher_class.return_value = mock_searcher
        
        memory = ConversationMemory()
        result = _handle_retrieval("Test question", memory, "test_session")
        
        assert "tidak ditemukan" in result["answer"]
        assert result["num_docs"] == 0
        assert result["search_performed"] is True
        assert result["results_found"] is False
    
    @patch('src.services.ai_services.extract_query_components')
    def test_handle_retrieval_extraction_error(self, mock_extract):
        """Test retrieval when query extraction fails"""
        from src.services.ai_services import _handle_retrieval
        from src.generation.memory import ConversationMemory
        
        # Setup mock to raise exception
        mock_extract.side_effect = Exception("Extraction failed")
        
        memory = ConversationMemory()
        
        with pytest.raises(RetrievalError, match="Failed to parse query"):
            _handle_retrieval("Test question", memory, "test_session")


if __name__ == "__main__":
    pytest.main([__file__])