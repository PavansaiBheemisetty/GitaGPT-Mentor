import logging
from functools import lru_cache

from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.services.auth_service import SupabaseAuthService
from app.services.chat_repository import AuthUser, ChatRepository
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)


@lru_cache
def get_embeddings_provider():
    """Preload embeddings model separately to reduce startup blocking."""
    from app.rag.embeddings import create_embedding_provider
    return create_embedding_provider(get_settings())


@lru_cache
def get_vector_store():
    """Preload FAISS vector store separately to reduce startup blocking."""
    from app.rag.vector_store import VectorStore
    settings = get_settings()
    store = VectorStore(settings.faiss_index_path, settings.faiss_metadata_path)
    store.load()
    return store


@lru_cache
def get_retriever():
    """Preload retriever (depends on embeddings + vector store)."""
    from app.rag.retriever import Retriever
    settings = get_settings()
    embeddings = get_embeddings_provider()
    store = get_vector_store()
    return Retriever(settings, embeddings, store)


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(get_settings(), repository=get_chat_repository())


@lru_cache
def get_chat_repository() -> ChatRepository:
    return ChatRepository(get_settings().database_url)


@lru_cache
def get_auth_service() -> SupabaseAuthService:
    settings = get_settings()
    return SupabaseAuthService(
        supabase_url=settings.supabase_url,
        supabase_anon_key=settings.supabase_anon_key,
        supabase_service_role_key=settings.supabase_service_role_key,
    )


def _bearer_token_from_header(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


async def get_optional_user(
    authorization: str | None = Header(default=None),
) -> AuthUser | None:
    token = _bearer_token_from_header(authorization)
    if not token:
        return None
    auth_service = get_auth_service()
    user = await auth_service.resolve_user(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        )
    return user


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> AuthUser:
    user = await get_optional_user(authorization)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user


def clear_service_cache() -> None:
    get_chat_service.cache_clear()
    get_chat_repository.cache_clear()
    get_auth_service.cache_clear()
