from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

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

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    retrieval_top_k: int = 6
    retrieval_min_score: float = 0.35
    max_message_chars: int = 4000
    max_history_turns: int = 6
    max_history_chars: int = 8000
    allow_empty_index: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
