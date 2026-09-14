"""
Unit tests for chain.py exception re-raising behavior.
"""

from unittest.mock import Mock, patch
import pytest

from src.generation.chain import RAGGenerator


class TestChainErrors:

    @patch("src.generation.chain.get_llm")
    def test_generate_re_raises_exception(self, mock_get_llm):
        """Pastikan RAGGenerator.generate() me-raise exception asli saat LLM gagal, tidak menelannya."""
        mock_llm = Mock()
        mock_llm.invoke.side_effect = TimeoutError("OpenAI API timed out")
        mock_get_llm.return_value = mock_llm

        generator = RAGGenerator()

        with pytest.raises(TimeoutError) as exc_info:
            generator.generate(
                question="Berapa lama batas pengerjaan skripsi?",
                context_documents=[],
            )

        assert "OpenAI API timed out" in str(exc_info.value)
