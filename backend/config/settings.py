from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import ValidationInfo
from typing import Optional, Literal
import os


def _find_env_file() -> str:
    """Cari file .env dari direktori project root."""
    # Cari dari lokasi file ini ke atas sampai ketemu .env
    current = Path(__file__).resolve().parent
    for _ in range(5):  # max 5 level ke atas
        env_path = current / ".env"
        if env_path.exists():
            return str(env_path)
        current = current.parent
    return ".env"  # fallback


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Info
    APP_NAME: str = "Chatbot KKP/PI Assistant"
    VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = Field(default=False, description="Enable debug mode")

    # OpenAI Configuration
    open_api_key: str = Field(..., description="OpenAI API Key")
    llm_model: str = Field(default="gpt-4o-mini", description="LLM model to use")
    embedding_model: str = Field(default="text-embedding-3-large", description="Embedding model")
    
    # OpenAI Rate Limiting
    openai_max_retries: int = Field(default=3, ge=1, le=10)
    openai_timeout: int = Field(default=60, ge=10, le=300)

    # Supabase Configuration
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_service_key: str = Field(..., description="Supabase service role key")

    # Database Tables
    table_parent_chunks: str = Field(default="parent_documents")
    table_child_chunks: str = Field(default="child_documents")
    table_user_quotas: str = Field(default="user_quotas")
    table_chat_logs: str = Field(default="chat_logs")
    table_conversation_sessions: str = Field(default="conversation_sessions")

    # Retrieval Configuration
    retrieval_top_k: int = Field(default=30, ge=5, le=100, description="Number of chunks to retrieve")
    rerank_top_n: int = Field(default=8, ge=3, le=20, description="Number of documents after reranking")
    max_parent_for_rerank: int = Field(default=8, ge=3, le=50, description="Max parents to send to reranker")
    min_parent_for_rerank: int = Field(default=3, ge=1, le=10, description="Min parents required to trigger reranker")
    rerank_min_top_score: float = Field(default=0.0, description="Minimum top score required to continue LLM generation")
    rerank_relative_gap: float = Field(default=2.5, description="Adaptive gap from top score to keep documents")
    bm25_weight: float = Field(default=0.4, ge=0.0, le=1.0, description="BM25 weight in hybrid search")
    dense_weight: float = Field(default=0.6, ge=0.0, le=1.0, description="Dense search weight")

    # Evaluation Configuration
    ragas_sample_size: int = Field(default=50, ge=10, le=500)
    ragas_timeout: int = Field(default=300, ge=60, le=600)

    # Cross-Encoder Configuration
    cross_encoder_model: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    cross_encoder_batch_size: int = Field(default=32, ge=1, le=128)

    # Hugging Face (Optional)
    hf_token: Optional[str] = Field(default=None, description="Hugging Face token for private models")

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_file: Optional[str] = Field(default=None, description="Log file path (optional)")

    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = Field(..., description="Telegram bot token")
    TELEGRAM_WEBHOOK_URL: str = Field(default="", description="Webhook URL for production")
    TELEGRAM_WEBHOOK_SECRET: str = Field(default="", description="Webhook secret")
    TELEGRAM_WEBHOOK_PATH: str = Field(default="/api/telegram/webhook")
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100, ge=1, le=100, description="Requests per day per user")
    RATE_LIMIT_WINDOW: int = Field(default=86400, ge=3600, le=604800, description="Rate limit window in seconds")

    # Performance Settings
    MAX_CONCURRENT_REQUESTS: int = Field(default=10, ge=1, le=50)
    REQUEST_TIMEOUT: int = Field(default=30, ge=10, le=120)
    
    # Memory Management
    MAX_ACTIVE_SESSIONS: int = Field(default=1000, ge=100, le=10000)
    SESSION_CLEANUP_INTERVAL: int = Field(default=3600, ge=300, le=7200)  # seconds
    USE_DATABASE_SESSIONS: bool = Field(default=True, description="Use database-backed sessions instead of in-memory")
    MAX_HISTORY_TURNS: int = Field(default=3, ge=1, le=10, description="Maximum number of conversation turns sent to LLM")

    @field_validator("bm25_weight", "dense_weight")
    @classmethod
    def validate_weights_sum(cls, v: float, info: ValidationInfo) -> float:
        """Ensure BM25 and dense weights sum to 1.0"""
        if info.field_name == "dense_weight" and "bm25_weight" in info.data:
            bm25_weight = info.data["bm25_weight"]
            if abs(v + bm25_weight - 1.0) > 0.001:
                raise ValueError(f"bm25_weight + dense_weight must equal 1.0, got {bm25_weight + v}")
        return v

    @field_validator("TELEGRAM_WEBHOOK_SECRET", mode='after')
    @classmethod
    def validate_webhook_secret(cls, value: str, info: ValidationInfo) -> str:
        """Validate webhook secret for production"""
        env = info.data.get("ENVIRONMENT", "development")
        if env == "production" and info.data.get("TELEGRAM_WEBHOOK_URL"):
            if not value or len(value) < 16:
                raise ValueError("TELEGRAM_WEBHOOK_SECRET is required and must be at least 16 chars in production")
        return value

    @field_validator("open_api_key", "supabase_service_key", "TELEGRAM_BOT_TOKEN")
    @classmethod
    def validate_required_secrets(cls, value: str) -> str:
        """Ensure required secrets are not empty"""
        if not value or value.strip() == "":
            raise ValueError("This field is required and cannot be empty")
        return value.strip()

    def get_openai_config(self) -> dict:
        """Get OpenAI client configuration"""
        return {
            "api_key": self.open_api_key,
            "max_retries": self.openai_max_retries,
            "timeout": self.openai_timeout,
        }

    def get_supabase_config(self) -> dict:
        """Get Supabase client configuration"""
        return {
            "url": self.supabase_url,
            "key": self.supabase_service_key,
        }

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT == "production"

    def is_development(self) -> bool:
        """Check if running in development"""
        return self.ENVIRONMENT == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance (loaded once)."""
    return Settings()