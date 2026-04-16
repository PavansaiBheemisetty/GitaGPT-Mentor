from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.rag.pdf_loader import extract_pdf_pages


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract sample PDF text for parser inspection.")
    parser.add_argument("--pages", type=int, default=15)
    parser.add_argument("--output", type=Path, default=Path("data/fixtures/local/extraction-sample.txt"))
    args = parser.parse_args()

    settings = get_settings()
    pages = extract_pdf_pages(settings.pdf_path, max_pages=args.pages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n\n".join(f"===== PAGE {page.page_number} =====\n{page.text}" for page in pages),
        encoding="utf-8",
    )
    print(f"Wrote extraction sample to {args.output}")


if __name__ == "__main__":
    main()
