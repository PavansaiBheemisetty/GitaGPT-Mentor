from functools import lru_cache

from app.core.config import get_settings
from app.services.chat_service import ChatService


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(get_settings())


def clear_service_cache() -> None:
    get_chat_service.cache_clear()
