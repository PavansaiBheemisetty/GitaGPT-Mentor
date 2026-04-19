import re
from collections import defaultdict

from app.models.corpus import VerseRecord
from app.rag.normalizer import clean_section_text
from app.rag.pdf_loader import ExtractedPage


VERSE_HEADING = re.compile(
    r"(?im)^\s*(?:TEXTS?|Texts?)\s+((?:\d+\.)?\d+(?:[-–]\d+)?)\s*$"
)
CHAPTER_HEADING = re.compile(r"(?im)^\s*-?\s*CHAPTER\s+(\d+)\s*-?\s*$")
TRANSLATION = re.compile(r"(?im)^\s*TRANSLATION\s*$")
PURPORT = re.compile(r"(?im)^\s*PURPORT\s*$")
NEXT_SECTION = re.compile(
    r"(?im)^\s*(TEXTS?\s+[\d.]+(?:[-–]\d+)?|-?\s*CHAPTER\s+\d+\s*-?|SYNONYMS|TRANSLATION|PURPORT)\s*$"
)


def parse_verses(pages: list[ExtractedPage]) -> list[VerseRecord]:
    chapter_by_page = _chapter_map(pages)
    page_text = "\n\n".join(f"\n[PAGE {p.page_number}]\n{p.text}" for p in pages)
    matches = list(VERSE_HEADING.finditer(page_text))
    records: list[VerseRecord] = []

    for index, match in enumerate(matches):
        verse_label = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(page_text)
        block = page_text[start:end]
        pages_for_block = _pages_in_block(block)
        chapter = _chapter_for_block(
            verse_label,
            pages_for_block,
            chapter_by_page,
            prefix=page_text[: match.start()],
        )
        translation = _extract_section(block, TRANSLATION, stop_at=PURPORT)
        purport = _extract_section(block, PURPORT, stop_at=NEXT_SECTION)
        warnings = []
        if not translation:
            warnings.append("missing_translation")
        if not purport:
            warnings.append("missing_purport")
        records.append(
            VerseRecord(
                chapter=chapter,
                verse=_normalize_verse_label(verse_label),
                translation=translation,
                purport=purport,
                source_pages=pages_for_block,
                extraction_warnings=warnings,
            )
        )
    return _dedupe_records(records)


def _chapter_map(pages: list[ExtractedPage]) -> dict[int, int]:
    current = 1
    mapping: dict[int, int] = {}
    for page in pages:
        found = CHAPTER_HEADING.search(page.text)
        if found:
            current = int(found.group(1))
        mapping[page.page_number] = current
    return mapping


def _chapter_for_block(
    verse_label: str, pages: list[int], chapter_by_page: dict[int, int], *, prefix: str = ""
) -> int:
    if "." in verse_label:
        return int(verse_label.split(".", 1)[0])
    if pages:
        return chapter_by_page.get(pages[0], 1)
    headings = list(CHAPTER_HEADING.finditer(prefix))
    if headings:
        return int(headings[-1].group(1))
    return 1


def _normalize_verse_label(label: str) -> str:
    if "." in label:
        return label.split(".", 1)[1]
    return label.replace("–", "-")


def _pages_in_block(block: str) -> list[int]:
    pages = [int(item) for item in re.findall(r"\[PAGE\s+(\d+)\]", block)]
    return sorted(set(pages))


def _extract_section(block: str, marker: re.Pattern[str], *, stop_at: re.Pattern[str]) -> str | None:
    found = marker.search(block)
    if not found:
        return None
    start = found.end()
    stop = stop_at.search(block, start)
    end = stop.start() if stop else len(block)
    text = re.sub(r"\[PAGE\s+\d+\]", "", block[start:end])
    text = clean_section_text(text)
    return text or None


def _dedupe_records(records: list[VerseRecord]) -> list[VerseRecord]:
    seen: dict[tuple[int, str], VerseRecord] = {}
    duplicates: defaultdict[tuple[int, str], int] = defaultdict(int)
    for record in records:
        key = (record.chapter, record.verse)
        if key in seen:
            duplicates[key] += 1
            existing = seen[key]
            existing.extraction_warnings.append("duplicate_verse")
            if not existing.translation and record.translation:
                existing.translation = record.translation
            if not existing.purport and record.purport:
                existing.purport = record.purport
            existing.source_pages = sorted(set(existing.source_pages + record.source_pages))
        else:
            seen[key] = record
    return list(seen.values())
