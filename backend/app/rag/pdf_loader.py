from dataclasses import dataclass
from pathlib import Path

from app.rag.normalizer import normalize_text


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


def extract_pdf_pages(path: Path, *, max_pages: int | None = None) -> list[ExtractedPage]:
    if not path.exists():
        raise FileNotFoundError(f"PDF not found at {path}")

    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is not installed. Install backend dependencies with `pip install -e .`."
        ) from exc

    pages: list[ExtractedPage] = []
    with fitz.open(path) as doc:
        limit = min(len(doc), max_pages) if max_pages else len(doc)
        for index in range(limit):
            page = doc[index]
            text = page.get_text("text", sort=True)
            if not text.strip():
                blocks = page.get_text("blocks", sort=True)
                text = "\n".join(str(block[4]) for block in blocks if len(block) >= 5)
            pages.append(ExtractedPage(page_number=index + 1, text=normalize_text(text)))
    return pages
