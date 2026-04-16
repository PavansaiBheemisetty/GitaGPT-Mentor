from app.rag.parser import parse_verses
from app.rag.pdf_loader import ExtractedPage


def test_parser_extracts_translation_and_purport():
    pages = [
        ExtractedPage(
            page_number=1,
            text="""CHAPTER 2
TEXT 47

TRANSLATION
You have a right to perform your duty.

PURPORT
This verse teaches steady action.

TEXT 48
TRANSLATION
Be steady.
PURPORT
Another purport.""",
        )
    ]
    records = parse_verses(pages)
    assert records[0].chapter == 2
    assert records[0].verse == "47"
    assert "perform your duty" in (records[0].translation or "")
    assert "steady action" in (records[0].purport or "")
