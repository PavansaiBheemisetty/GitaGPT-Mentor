import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_chat_repository
from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.core.config import get_settings

# ── Configure root logger so ALL app loggers print to the terminal ────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)
# Quiet noisy third-party loggers
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # ── Preload heavy resources at startup to eliminate cold-start latency ──
    logger.info("🔥 Preloading embeddings model...")
    try:
        from app.api.deps import get_embeddings_provider
        get_embeddings_provider()
        logger.info("✅ Embeddings model preloaded.")
    except Exception as exc:
        logger.warning(
            "⚠️  Embeddings preload failed: %s. Resources will load lazily on first request.",
            exc,
        )

    logger.info("🔥 Preloading FAISS retriever...")
    try:
        from app.api.deps import get_retriever
        get_retriever()
        logger.info("✅ FAISS retriever preloaded.")
    except Exception as exc:
        logger.warning(
            "⚠️  FAISS retriever preload failed: %s. Resources will load lazily on first request.",
            exc,
        )

    logger.info("✅ Startup preload complete.")

    yield

    repository = get_chat_repository()
    await repository.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="GitaGPT API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(chat_router)
    return app


app = create_app()
