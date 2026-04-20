import json
from urllib.parse import urlparse

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


def _is_configured(value: str | None) -> bool:
    return bool(value and value.strip())


def _endpoint_host(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc or parsed.path or None


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    index_exists = settings.faiss_index_path.exists() and settings.faiss_metadata_path.exists()
    corpus_report = None
    if settings.corpus_report_path.exists():
        corpus_report = json.loads(settings.corpus_report_path.read_text(encoding="utf-8"))
    return {
        "status": "ok" if index_exists or settings.allow_empty_index else "setup_required",
        "index_exists": index_exists,
        "index_path": str(settings.faiss_index_path),
        "metadata_path": str(settings.faiss_metadata_path),
        "embedding_provider": settings.embedding_provider,
        "llm_provider": settings.llm_provider,
        "llm_diagnostics": {
            "primary": settings.llm_provider,
            "providers": {
                "groq": {
                    "configured": _is_configured(settings.groq_api_key),
                    "model": settings.groq_model,
                    "endpoint_host": _endpoint_host(settings.groq_base_url),
                },
                "modal": {
                    "configured": _is_configured(settings.modal_api_key),
                    "model": settings.modal_model,
                    "endpoint_host": _endpoint_host(settings.modal_base_url),
                },
                "openrouter": {
                    "configured": _is_configured(settings.openrouter_api_key),
                    "model": settings.openrouter_model,
                    "endpoint_host": _endpoint_host(settings.openrouter_base_url),
                },
            },
        },
        "corpus": corpus_report,
    }
