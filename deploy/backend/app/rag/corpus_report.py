import json
from collections import Counter, defaultdict
from pathlib import Path

from app.models.corpus import VerseRecord


def build_corpus_report(records: list[VerseRecord]) -> dict:
    warnings = Counter(warning for r in records for warning in r.extraction_warnings)
    by_chapter: dict[int, dict[str, int]] = defaultdict(lambda: {"verses": 0, "translations": 0, "purports": 0})
    for record in records:
        units = _verse_units(record.verse)
        chapter = by_chapter[record.chapter]
        chapter["verses"] += units
        if record.translation:
            chapter["translations"] += units
        if record.purport:
            chapter["purports"] += units

    return {
        "total_records": len(records),
        "total_verses": sum(_verse_units(r.verse) for r in records),
        "translations": sum(_verse_units(r.verse) for r in records if r.translation),
        "purports": sum(_verse_units(r.verse) for r in records if r.purport),
        "warnings": dict(warnings),
        "by_chapter": {str(k): v for k, v in sorted(by_chapter.items())},
        "sample_warnings": [
            {
                "chapter": r.chapter,
                "verse": r.verse,
                "warnings": r.extraction_warnings,
                "source_pages": r.source_pages,
            }
            for r in records
            if r.extraction_warnings
        ][:25],
    }


def enforce_corpus_gates(
    report: dict,
    *,
    expected_verses: int = 699,
    min_translations: int = 650,
    min_purports: int = 500,
) -> None:
    failures = []
    if report["total_verses"] < expected_verses:
        failures.append(f"expected at least {expected_verses} verse units, got {report['total_verses']}")
    if report["translations"] < min_translations:
        failures.append(f"expected at least {min_translations} translations, got {report['translations']}")
    if report["purports"] < min_purports:
        failures.append(f"expected at least {min_purports} purports, got {report['purports']}")
    if failures:
        raise ValueError("Corpus gates failed: " + "; ".join(failures))


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def _verse_units(label: str) -> int:
    normalized = label.replace("–", "-")
    if "-" not in normalized:
        return 1
    start, end = normalized.split("-", 1)
    if start.isdigit() and end.isdigit():
        return int(end) - int(start) + 1
    return 1
