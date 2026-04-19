from app.models.chat import Citation, RetrievedChunk


def backend_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    citations: list[Citation] = []
    seen = set()
    for chunk in chunks:
        key = (chunk.chapter, chunk.verse, chunk.type)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                chapter=chunk.chapter,
                verse=chunk.verse,
                type=chunk.type,
                chunk_id=chunk.chunk_id,
                source_pages=chunk.source_pages,
                preview=chunk.preview,
                score=chunk.score,
            )
        )
    return citations
