import json

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


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
        "corpus": corpus_report,
    }
