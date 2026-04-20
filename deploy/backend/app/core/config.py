from functools import lru_cache
import json
from pathlib import Path

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    auth_required: bool = False

    database_url: str | None = None
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None

    pdf_path: Path = Path("data/raw/Bhagavad-Gita As It Is.pdf")
    processed_verses_path: Path = Path("data/processed/verses.jsonl")
    processed_chunks_path: Path = Path("data/processed/chunks.jsonl")
    corpus_report_path: Path = Path("data/processed/corpus_report.json")
    faiss_index_path: Path = Path("data/index/faiss.index")
    faiss_metadata_path: Path = Path("data/index/metadata.json")

    embedding_provider: str = "sentence-transformers"
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dimension: int | None = 768
    embedding_device: str = "cpu"
    vector_store_provider: str = "faiss"

    llm_provider: str = "groq"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    modal_base_url: str = "https://api.us-west-2.modal.direct/v1"
    modal_api_key: str | None = None
    modal_model: str = "zai-org/GLM-5.1-FP8"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str | None = None
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct:free"
    hf_token: str | None = None

    retrieval_top_k: int = 6
    retrieval_min_score: float = 0.35
    max_message_chars: int = 4000
    max_history_turns: int = 6
    max_history_chars: int = 8000
    memory_context_window: int = 5
    stream_word_delay_ms: int = 16
    allow_empty_index: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        origins: list[str]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                origins = []
            elif raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
                else:
                    if isinstance(parsed, list):
                        origins = [str(origin).strip() for origin in parsed if str(origin).strip()]
                    else:
                        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
            else:
                origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        else:
            origins = [origin.strip() for origin in value if origin and origin.strip()]

        # Dev convenience: if one loopback host is present, allow the other too.
        expanded = set(origins)
        for origin in list(expanded):
            if "localhost" in origin:
                expanded.add(origin.replace("localhost", "127.0.0.1"))
            if "127.0.0.1" in origin:
                expanded.add(origin.replace("127.0.0.1", "localhost"))
        return sorted(expanded)

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_llm_provider(cls, value: str | None) -> str:
        if value is None:
            return "groq"
        normalized = str(value).strip().lower()
        return normalized or "groq"

    @field_validator(
        "groq_base_url",
        "modal_base_url",
        "openrouter_base_url",
        mode="before",
    )
    @classmethod
    def normalize_base_urls(cls, value: str | None, info: ValidationInfo) -> str:
        defaults = {
            "groq_base_url": "https://api.groq.com/openai/v1",
            "modal_base_url": "https://api.us-west-2.modal.direct/v1",
            "openrouter_base_url": "https://openrouter.ai/api/v1",
        }
        fallback = defaults[info.field_name]
        if value is None:
            return fallback
        normalized = str(value).strip()
        return normalized or fallback

    @field_validator(
        "groq_api_key",
        "modal_api_key",
        "openrouter_api_key",
        mode="before",
    )
    @classmethod
    def normalize_string_settings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
