from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import ValidationInfo
from typing import Optional, Literal


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
    CORS_ALLOWED_ORIGINS: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ]
    )
    CORS_ALLOWED_ORIGIN_REGEX: str = Field(
        default=r"https://rag-chatbot-.*\.vercel\.app"
    )

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
    table_mahasiswa_accounts: str = Field(default="mahasiswa_accounts")

    # Retrieval Configuration
    retrieval_top_k: int = Field(default=30, ge=5, le=100, description="Number of chunks to retrieve")
    rerank_top_n: int = Field(default=8, ge=3, le=20, description="Number of documents after reranking")
    max_parent_for_rerank: int = Field(default=8, ge=3, le=50, description="Max parents to send to reranker")
    min_parent_for_rerank: int = Field(default=3, ge=1, le=10, description="Min parents required to trigger reranker")
    rerank_min_top_score: float = Field(default=0.0, description="Minimum top score required to continue LLM generation")
    rerank_relative_gap: float = Field(default=2.5, description="Adaptive gap from top score to keep documents")
    bm25_weight: float = Field(default=0.4, ge=0.0, le=1.0, description="BM25 weight in hybrid search")
    dense_weight: float = Field(default=0.6, ge=0.0, le=1.0, description="Dense search weight")
    dense_fallback_threshold: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum similarity threshold for dense-only fallback search")

    # Evaluation Configuration
    ragas_sample_size: int = Field(default=50, ge=10, le=500)
    ragas_timeout: int = Field(default=300, ge=60, le=600)
    EVALUATION_MODEL: Optional[str] = Field(
        default=None,
        description="Model evaluator; uses LLM_MODEL when unset",
    )
    EVALUATION_DOCUMENT_MANIFEST: str = Field(
        default="config/evaluation_documents.yaml"
    )
    EVALUATION_PAGE_WINDOW: int = Field(default=3, ge=1, le=10)
    EVALUATION_QUESTION_BATCH_SIZE: int = Field(default=10, ge=1, le=25)
    EVALUATION_MAX_EVIDENCE_PER_CASE: int = Field(default=5, ge=1, le=20)
    EVALUATION_AGENT_ENABLED: bool = Field(default=False)

    # Cross-Encoder Configuration
    cross_encoder_model: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    cross_encoder_batch_size: int = Field(default=32, ge=1, le=128)
    MAX_CONTEXT_TOKENS: int = Field(default=12000, ge=1000, le=100000)

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
    TIMEZONE: str = Field(default="Asia/Makassar", description="Zona waktu aplikasi untuk kuota & tanggal (default: Asia/Makassar / WITA)")
    
    # Proxy Configuration
    TRUSTED_PROXIES: list[str] = Field(
        default=["127.0.0.1", "::1"],
        description="List of trusted proxy IP addresses that can send X-Forwarded-For headers"
    )

    # Authentication Configuration
    JWT_SECRET_KEY: str = Field(default="super-secret-key-change-in-production", description="Secret key for JWT generation")
    JWT_ALGORITHM: str = Field(default="HS256", description="Algorithm for JWT generation")
    JWT_EXPIRATION_MINUTES: int = Field(default=30, ge=5, le=10080, description="JWT access-token expiration time in minutes")
    JWT_CLOCK_SKEW_SECONDS: int = Field(default=30, ge=0, le=300)
    ENABLE_REFRESH_TOKENS: bool = Field(default=False)
    REFRESH_TOKEN_EXPIRATION_DAYS: int = Field(default=14, ge=1, le=90)
    REFRESH_COOKIE_NAME: str = Field(default="refresh_token")
    ADMIN_REFRESH_COOKIE_NAME: str = Field(default="admin_refresh_token")
    REFRESH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = Field(default="lax")
    REFRESH_COOKIE_DOMAIN: Optional[str] = Field(default=None)
    GOOGLE_CLIENT_ID: str = Field(default="", description="Google OAuth Client ID")

    # Performance Settings
    MAX_CONCURRENT_REQUESTS: int = Field(default=10, ge=1, le=50)
    REQUEST_TIMEOUT: int = Field(default=30, ge=10, le=120)
    REQUEST_QUEUE_TIMEOUT: float = Field(default=1.0, ge=0.1, le=30.0)
    
    # Memory Management
    MAX_ACTIVE_SESSIONS: int = Field(default=1000, ge=100, le=10000)
    SESSION_CLEANUP_INTERVAL: int = Field(default=3600, ge=300, le=7200)  # seconds
    USE_DATABASE_SESSIONS: bool = Field(default=True, description="Use database-backed sessions instead of in-memory")
    MEMORY_MAX_HISTORY_TOKENS: int = Field(
        default=2500,
        ge=500,
        le=16000,
        description="Token budget for conversation summary and recent messages",
    )
    MEMORY_MIN_RECENT_TURNS: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Minimum complete recent Q&A pairs retained after summarization",
    )
    MEMORY_SUMMARY_MAX_TOKENS: int = Field(
        default=500,
        ge=100,
        le=4000,
        description="Maximum output tokens for conversation summarization",
    )

    # Monitoring & Observability
    ENABLE_REQUEST_METRICS: bool = Field(default=True, description="Aktifkan pencatatan request_metrics")

    # Distributed tracing. Tanpa OTEL_EXPORTER_OTLP_ENDPOINT, span tetap
    # tersedia di process dan tidak dikirim ke layanan eksternal.
    OTEL_ENABLED: bool = Field(default=False)
    OTEL_SERVICE_NAME: str = Field(default="graduation-assistant-backend")
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = Field(default=None)
    OTEL_EXPORTER_OTLP_HEADERS: Optional[str] = Field(default=None)

    @field_validator("bm25_weight", "dense_weight")
    @classmethod
    def validate_weights_sum(cls, v: float, info: ValidationInfo) -> float:
        """Ensure BM25 and dense weights sum to 1.0"""
        if info.field_name == "dense_weight" and "bm25_weight" in info.data:
            bm25_weight = info.data["bm25_weight"]
            if abs(v + bm25_weight - 1.0) > 0.001:
                raise ValueError(f"bm25_weight + dense_weight must equal 1.0, got {bm25_weight + v}")
        return v

    @model_validator(mode="after")
    def validate_memory_token_limits(self) -> "Settings":
        if self.MEMORY_SUMMARY_MAX_TOKENS >= self.MEMORY_MAX_HISTORY_TOKENS:
            raise ValueError(
                "MEMORY_SUMMARY_MAX_TOKENS harus lebih kecil dari "
                "MEMORY_MAX_HISTORY_TOKENS"
            )
        return self

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Tolak konfigurasi autentikasi yang tidak aman di production."""
        if self.ENVIRONMENT != "production":
            return self

        insecure_defaults = {
            "super-secret-key-change-in-production",
            "change-me",
            "secret",
        }
        if (
            self.JWT_SECRET_KEY.strip().lower() in insecure_defaults
            or len(self.JWT_SECRET_KEY.encode("utf-8")) < 32
        ):
            raise ValueError(
                "JWT_SECRET_KEY production wajib unik dan minimal 32 byte"
            )
        if not self.ENABLE_REFRESH_TOKENS:
            raise ValueError(
                "ENABLE_REFRESH_TOKENS wajib aktif di production setelah migration auth dijalankan"
            )
        if self.JWT_EXPIRATION_MINUTES > 60:
            raise ValueError(
                "JWT_EXPIRATION_MINUTES production maksimal 60 menit"
            )
        return self

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
