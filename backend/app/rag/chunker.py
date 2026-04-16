import re

from app.models.corpus import ChunkRecord, VerseRecord


def chunk_verses(records: list[VerseRecord], *, target_words: int = 320) -> list[ChunkRecord]:
    chunks: list[ChunkRecord] = []
    for record in records:
        if record.translation:
            text = _with_prefix(record, "translation", record.translation)
            chunks.append(
                ChunkRecord(
                    chunk_id=f"bg-{record.chapter}-{record.verse}-translation",
                    chapter=record.chapter,
                    verse=record.verse,
                    type="translation",
                    text=text,
                    source_pages=record.source_pages,
                    char_start=0,
                    char_end=len(record.translation),
                    token_estimate=_estimate_tokens(text),
                )
            )
        if record.purport:
            for idx, part in enumerate(_split_purport(record.purport, target_words=target_words), 1):
                text = _with_prefix(record, "purport", part)
                chunks.append(
                    ChunkRecord(
                        chunk_id=f"bg-{record.chapter}-{record.verse}-purport-{idx:03d}",
                        chapter=record.chapter,
                        verse=record.verse,
                        type="purport",
                        text=text,
                        source_pages=record.source_pages,
                        char_start=record.purport.find(part),
                        char_end=record.purport.find(part) + len(part),
                        token_estimate=_estimate_tokens(text),
                    )
                )
    return chunks


def _with_prefix(record: VerseRecord, chunk_type: str, text: str) -> str:
    return f"Bhagavad Gita {record.chapter}.{record.verse} {chunk_type}:\n{text.strip()}"


def _split_purport(text: str, *, target_words: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    parts: list[str] = []
    current: list[str] = []
    count = 0
    for paragraph in paragraphs or [text]:
        words = paragraph.split()
        if current and count + len(words) > target_words:
            parts.append("\n\n".join(current))
            current = [paragraph]
            count = len(words)
        else:
            current.append(paragraph)
            count += len(words)
    if current:
        parts.append("\n\n".join(current))
    return parts


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.33))
