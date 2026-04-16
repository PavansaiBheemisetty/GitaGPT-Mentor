from app.models.corpus import VerseRecord
from app.rag.chunker import chunk_verses


def test_chunker_preserves_metadata():
    chunks = chunk_verses(
        [
            VerseRecord(
                chapter=2,
                verse="47",
                translation="Do your duty.",
                purport="First paragraph.\n\nSecond paragraph.",
                source_pages=[10],
            )
        ],
        target_words=2,
    )
    assert chunks[0].chapter == 2
    assert chunks[0].verse == "47"
    assert chunks[0].type == "translation"
    assert chunks[0].source_pages == [10]
    assert any(chunk.type == "purport" for chunk in chunks)
