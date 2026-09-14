#!/usr/bin/env python
"""Developer-only helper: extracts raw text from a downloaded PDF so it can
be reviewed and turned into a knowledge_docs/*.md file for
scripts/ingest_knowledge.py.

This deliberately does NOT auto-ingest anything - PDF text extraction is
messy (broken line wraps, headers/footers repeated on every page, page
numbers mid-sentence) and always needs a human pass before it's fit to
chunk. Treat this script's output as a rough draft, not a final document:
open it, clean it up, add your own `##` headings for the sections you
actually want in the knowledge base (you do not have to keep the whole
document - excerpting the genuinely useful practical guidance is both
more legally conservative than republishing an entire manual verbatim,
and produces better chunks than a wall of undifferentiated text).

Usage:
    python -m scripts.pdf_to_text --file raw_pdfs/water_management_uga.pdf --out knowledge_docs/water_management.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pypdf import PdfReader


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"<!-- page {i} -->\n{text}")
    return "\n\n".join(pages)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", required=True, help="Path to the downloaded PDF")
    parser.add_argument("--out", required=True, help="Where to write the extracted .md/.txt draft")
    args = parser.parse_args()

    text = extract_text(Path(args.file))
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"Wrote {len(text)} characters to {args.out}")
    print("This is a raw draft - open it, remove headers/footers/page-number noise, add real ## headings, and trim to the sections you actually want before ingesting.")


if __name__ == "__main__":
    main()
