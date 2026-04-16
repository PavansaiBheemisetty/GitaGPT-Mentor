from app.models.chat import RetrievedChunk
from app.rag.citations import backend_citations


def test_backend_citations_are_deduped_from_retrieved_chunks():
    chunks = [
        RetrievedChunk(
            chunk_id="a",
            chapter=2,
            verse="47",
            type="translation",
            text="text",
            score=0.9,
            source_pages=[1],
        ),
        RetrievedChunk(
            chunk_id="b",
            chapter=2,
            verse="47",
            type="translation",
            text="text again",
            score=0.8,
            source_pages=[1],
        ),
    ]
    citations = backend_citations(chunks)
    assert len(citations) == 1
    assert citations[0].chunk_id == "a"
