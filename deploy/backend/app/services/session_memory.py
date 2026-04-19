from collections import defaultdict, deque
from threading import Lock

from app.models.chat import RetrievedChunk
from app.rag.theme_router import expand_verse_label


class ConversationVerseMemory:
    def __init__(self, window_size: int = 24) -> None:
        self.window_size = window_size
        self._store: dict[str, deque[tuple[int, str]]] = defaultdict(lambda: deque(maxlen=window_size))
        self._lock = Lock()

    def recent_verses(self, conversation_id: str | None) -> set[tuple[int, str]]:
        if not conversation_id:
            return set()
        with self._lock:
            return set(self._store.get(conversation_id, ()))

    def remember(self, conversation_id: str | None, chunks: list[RetrievedChunk]) -> None:
        if not conversation_id:
            return
        with self._lock:
            bucket = self._store[conversation_id]
            for chunk in chunks:
                for verse in expand_verse_label(chunk.verse):
                    bucket.append((chunk.chapter, verse))
