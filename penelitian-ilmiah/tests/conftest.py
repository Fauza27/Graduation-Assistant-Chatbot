"""
Pytest configuration and fixtures
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from typing import Generator, AsyncGenerator

from config.settings import Settings


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings() -> Settings:
    """Mock settings for testing"""
    return Settings(
        open_api_key="test-key",
        supabase_url="https://test.supabase.co",
        supabase_service_key="test-service-key",
        TELEGRAM_BOT_TOKEN="test-bot-token",
        ENVIRONMENT="testing",
        DEBUG=True,
        retrieval_top_k=5,
        rerank_top_n=3,
    )


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    client = Mock()
    client.embeddings = Mock()
    client.embeddings.create = AsyncMock(return_value=Mock(
        data=[Mock(embedding=[0.1] * 1536)]
    ))
    client.chat = Mock()
    client.chat.completions = Mock()
    client.chat.completions.create = AsyncMock(return_value=Mock(
        choices=[Mock(message=Mock(content="Test response"))]
    ))
    return client


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client"""
    client = Mock()
    client.table = Mock(return_value=Mock(
        select=Mock(return_value=Mock(
            execute=Mock(return_value=Mock(data=[]))
        ))
    ))
    return client


@pytest.fixture
def sample_documents():
    """Sample documents for testing"""
    return [
        {
            "parent_id": "doc1",
            "title": "Syarat PI",
            "content": "Syarat untuk mengambil PI adalah minimal 120 SKS",
            "section": "BAB II",
            "cross_encoder_score": 0.9
        },
        {
            "parent_id": "doc2", 
            "title": "Syarat KKP",
            "content": "Syarat untuk mengambil KKP adalah minimal 100 SKS",
            "section": "BAB III",
            "cross_encoder_score": 0.8
        }
    ]


@pytest.fixture
def sample_questions():
    """Sample questions for testing"""
    return [
        "Apa syarat SKS minimal untuk PI?",
        "Berapa IP minimal untuk KKP?",
        "Siapa dosen pembimbing PI?",
        "Bagaimana format laporan KKP?"
    ]