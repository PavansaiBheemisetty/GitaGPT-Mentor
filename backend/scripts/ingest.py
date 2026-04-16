from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.models.corpus import ChunkRecord, VerseRecord
from app.rag.chunker import chunk_verses
from app.rag.corpus_report import build_corpus_report, enforce_corpus_gates, write_report
from app.rag.embeddings import create_embedding_provider
from app.rag.parser import parse_verses
from app.rag.pdf_loader import extract_pdf_pages
from app.rag.vector_store import VectorStore


def main() -> None:
    settings = get_settings()
    pages = extract_pdf_pages(settings.pdf_path)
    verses = parse_verses(pages)
    report = build_corpus_report(verses)
    write_report(settings.corpus_report_path, report)
    enforce_corpus_gates(report)

    chunks = chunk_verses(verses)
    _write_jsonl(settings.processed_verses_path, verses)
    _write_jsonl(settings.processed_chunks_path, chunks)

    embeddings = create_embedding_provider(settings)
    vectors = embeddings.embed_texts([chunk.text for chunk in chunks])
    store = VectorStore(settings.faiss_index_path, settings.faiss_metadata_path)
    store.build(
        vectors,
        chunks,
        provider=settings.vector_store_provider,
        metadata={
            "embedding_provider": settings.embedding_provider,
            "embedding_model": embeddings.model_name,
            "embedding_dimension": embeddings.dimension,
            "similarity_metric": "inner_product",
            "normalize": True,
            "retrieval_min_score": settings.retrieval_min_score,
            "chunk_count": len(chunks),
        },
    )
    print(f"Ingested {len(verses)} verses and {len(chunks)} chunks.")
    print(f"Corpus report: {settings.corpus_report_path}")
    print(f"Index: {settings.faiss_index_path}")


def _write_jsonl(path: Path, records: list[VerseRecord] | list[ChunkRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
