from app.core.config import Settings
from app.models.chat import RetrievedChunk
from app.rag.embeddings import EmbeddingProvider
from app.rag.theme_router import chunk_matches_seed, theme_seed_verses
from app.rag.vector_store import VectorStore


class Retriever:
    def __init__(self, settings: Settings, embeddings: EmbeddingProvider, store: VectorStore) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self.store = store

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        theme: str = "general",
        avoid_verses: set[tuple[int, str]] | None = None,
    ) -> list[RetrievedChunk]:
        requested_k = top_k or self.settings.retrieval_top_k
        query_vector = self.embeddings.embed_texts([query])[0]
        candidate_k = max(requested_k * 8, requested_k + 12)
        raw_results = self.store.search(query_vector, top_k=candidate_k)
        reranked = _rerank(
            raw_results,
            theme=theme,
            avoid_verses=avoid_verses or set(),
        )
        diverse = _select_diverse(reranked, top_k=requested_k)
        chunks: list[RetrievedChunk] = []
        for result, adjusted_score in diverse:
            if adjusted_score < self.settings.retrieval_min_score:
                continue
            chunk = result.chunk
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    chapter=chunk.chapter,
                    verse=chunk.verse,
                    type=chunk.type,
                    text=chunk.text,
                    score=adjusted_score,
                    source_pages=chunk.source_pages,
                )
            )
        return chunks


def _rerank(results, *, theme: str, avoid_verses: set[tuple[int, str]]):
    seed_refs = theme_seed_verses(theme)
    rescored = []
    for result in results:
        adjusted = result.score
        chunk = result.chunk
        if chunk_matches_seed(chapter=chunk.chapter, verse_label=chunk.verse, seed_refs=seed_refs):
            adjusted += 0.16

        if chunk.type == "translation":
            adjusted += 0.02
        elif chunk.type == "purport":
            adjusted += 0.01

        if _chunk_is_recent(chunk.chapter, chunk.verse, avoid_verses):
            adjusted -= 0.08

        rescored.append((result, adjusted))

    rescored.sort(key=lambda item: item[1], reverse=True)
    return rescored


def _select_diverse(scored_results, *, top_k: int):
    grouped: dict[tuple[int, str], dict[str, tuple[object, float]]] = {}
    for result, score in scored_results:
        ref = (result.chunk.chapter, result.chunk.verse)
        bucket = grouped.setdefault(ref, {})
        current = bucket.get(result.chunk.type)
        if current is None or score > current[1]:
            bucket[result.chunk.type] = (result, score)

    ranked_refs = sorted(
        grouped.keys(),
        key=lambda ref: max(item[1] for item in grouped[ref].values()),
        reverse=True,
    )

    selected = []
    selected_chunk_ids: set[str] = set()
    for ref in ranked_refs:
        if len(selected) >= top_k:
            break
        per_type = grouped[ref]
        for chunk_type in ("translation", "purport"):
            candidate = per_type.get(chunk_type)
            if not candidate:
                continue
            result, score = candidate
            if result.chunk.chunk_id in selected_chunk_ids:
                continue
            selected.append((result, score))
            selected_chunk_ids.add(result.chunk.chunk_id)
            if len(selected) >= top_k:
                break

    if len(selected) < top_k:
        for result, score in scored_results:
            if result.chunk.chunk_id in selected_chunk_ids:
                continue
            selected.append((result, score))
            selected_chunk_ids.add(result.chunk.chunk_id)
            if len(selected) >= top_k:
                break

    return selected


def _chunk_is_recent(chapter: int, verse_label: str, recent: set[tuple[int, str]]) -> bool:
    normalized = verse_label.replace("–", "-")
    if "-" not in normalized:
        return (chapter, normalized) in recent

    start, end = normalized.split("-", 1)
    if start.isdigit() and end.isdigit():
        for value in range(int(start), int(end) + 1):
            if (chapter, str(value)) in recent:
                return True
        return False
    return (chapter, normalized) in recent

