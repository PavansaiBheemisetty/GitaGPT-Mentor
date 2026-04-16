import pytest

from app.models.corpus import VerseRecord
from app.rag.corpus_report import build_corpus_report, enforce_corpus_gates


def test_corpus_report_counts_sections():
    report = build_corpus_report(
        [VerseRecord(chapter=1, verse="1-2", translation="t", purport=None, extraction_warnings=["x"])]
    )
    assert report["total_records"] == 1
    assert report["total_verses"] == 2
    assert report["translations"] == 2
    assert report["purports"] == 0
    assert report["warnings"]["x"] == 1


def test_corpus_gates_fail_on_low_counts():
    with pytest.raises(ValueError):
        enforce_corpus_gates({"total_verses": 1, "translations": 1, "purports": 0})
