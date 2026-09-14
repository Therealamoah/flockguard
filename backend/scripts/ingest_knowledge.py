#!/usr/bin/env python
"""Developer/admin-only CLI for adding curated poultry reference documents
to the RAG knowledge base (app/services/knowledge_service.py).

There is no farmer-facing upload path, and no API endpoint for this - by
design (see section 45 of the architecture spec this was built from):
normal users must never be able to add content to the global knowledge
base. This script is meant to be run locally by whoever is adding a
document, against a real Firestore project (it needs real credentials
configured the same way the backend does - see backend/.env.example).

Usage
-----

1. Prepare a plain-text or Markdown source file for the document, and a
   metadata JSON file next to it, e.g. `water_management.json`:

    {
      "document_id": "fao-water-mgmt-2019",
      "title": "Water Management in Poultry Production",
      "publisher": "FAO",
      "category": "water_management",
      "production_type": "broiler",
      "source_type": "government",
      "source_url": "https://...",
      "publication_date": "2019",
      "version": "1",
      "usage_permission": "approved"
    }

   `usage_permission` must be set deliberately by whoever is adding the
   document, after actually confirming the license allows this use - this
   script never assumes a publicly downloadable file may be reused.

2. Ingest (chunks the file, writes it disabled/pending by default):

    python -m scripts.ingest_knowledge ingest \
        --file water_management.md --metadata water_management.json

3. Test retrieval against the pending document directly (bypasses the
   enabled/approved filter, for review purposes only):

    python -m scripts.ingest_knowledge test-retrieval \
        --document-id fao-water-mgmt-2019 --query "drinker function"

4. Once you've reviewed the content and confirmed usage_permission is
   genuinely "approved", enable it for production retrieval:

    python -m scripts.ingest_knowledge approve \
        --document-id fao-water-mgmt-2019 --reviewed-by "you@example.com"

5. To pull a document back out of production retrieval later (without
   losing its history) - guidance changes over time:

    python -m scripts.ingest_knowledge disable --document-id fao-water-mgmt-2019
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.firestore import get_firestore_client  # noqa: E402
from app.services.knowledge_service import (  # noqa: E402
    KnowledgeChunk,
    KnowledgeDocument,
    SourceType,
    add_chunk,
    add_document,
    approve_document,
    disable_document,
    knowledge_chunks_ref,
    search_poultry_knowledge,
)

_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)
_MAX_CHUNK_CHARS = 1500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _section_aware_chunks(text: str) -> list[tuple[str | None, str]]:
    """Splits on markdown headings when present (preferred - keeps a
    document's own structure, e.g. "Water Management" / "Feed Management"
    sections, intact), falling back to paragraph grouping otherwise. Each
    result is (section_title_or_None, chunk_text). Long sections are
    further split at paragraph boundaries so no chunk is unreasonably big,
    without ever splitting mid-paragraph.
    """
    headings = list(_HEADING_RE.finditer(text))
    sections: list[tuple[str | None, str]] = []

    if headings:
        for i, match in enumerate(headings):
            title = match.group(1).strip()
            start = match.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            body = text[start:end].strip()
            if body:
                sections.append((title, body))
    else:
        sections = [(None, text.strip())]

    chunks: list[tuple[str | None, str]] = []
    for title, body in sections:
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        current = ""
        for para in paragraphs:
            candidate = f"{current}\n\n{para}".strip() if current else para
            if len(candidate) > _MAX_CHUNK_CHARS and current:
                chunks.append((title, current))
                current = para
            else:
                current = candidate
        if current:
            chunks.append((title, current))
    return chunks


def cmd_ingest(args: argparse.Namespace) -> None:
    metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
    required = {"document_id", "title", "category", "source_type", "usage_permission"}
    missing = required - metadata.keys()
    if missing:
        raise SystemExit(f"metadata file is missing required fields: {sorted(missing)}")

    text = Path(args.file).read_text(encoding="utf-8")
    now = _now_iso()

    doc = KnowledgeDocument(
        document_id=metadata["document_id"],
        title=metadata["title"],
        publisher=metadata.get("publisher"),
        category=metadata["category"],
        production_type=metadata.get("production_type"),
        breed=metadata.get("breed"),
        country_or_region=metadata.get("country_or_region"),
        publication_date=metadata.get("publication_date"),
        version=metadata.get("version"),
        source_url=metadata.get("source_url"),
        source_type=SourceType(metadata["source_type"]),
        license_status=metadata.get("license_status", "review_required"),
        usage_permission=metadata["usage_permission"],
        enabled=False,  # never enabled by ingestion alone - see `approve`
        created_at=now,
        updated_at=now,
    )

    db = get_firestore_client()
    add_document(db, doc)

    chunks = _section_aware_chunks(text)
    for i, (section, content) in enumerate(chunks):
        chunk = KnowledgeChunk(
            chunk_id=f"{doc.document_id}__{i:03d}",
            document_id=doc.document_id,
            title=doc.title,
            publisher=doc.publisher,
            category=doc.category,
            section=section,
            page=None,  # set manually afterward if the source has real page numbers
            content=content,
            source_url=doc.source_url,
            version=doc.version,
            enabled=True,
        )
        add_chunk(db, chunk)

    print(f"Ingested {len(chunks)} chunk(s) for document '{doc.document_id}'.")
    print("Status: PENDING / DISABLED - not retrievable in production yet.")
    print(f"Review the content, then run: python -m scripts.ingest_knowledge approve --document-id {doc.document_id} --reviewed-by <you>")


def cmd_test_retrieval(args: argparse.Namespace) -> None:
    db = get_firestore_client()
    # Direct chunk read for review purposes - bypasses the production
    # enabled/approved filter that search_poultry_knowledge enforces, since
    # the whole point here is to review a document BEFORE approving it.
    all_chunks = [
        c.to_dict() for c in knowledge_chunks_ref(db).where("document_id", "==", args.document_id).stream()
    ]
    if not all_chunks:
        print(f"No chunks found for document_id '{args.document_id}' - did you run `ingest` first?")
        return

    # Any-word match (not "the whole query as one literal substring", which
    # is nearly useless for a multi-word query) - good enough for a human
    # reviewer eyeballing content, not meant to mirror production ranking.
    query_words = [w for w in args.query.lower().split() if len(w) > 2]
    matches = [c for c in all_chunks if any(w in c.get("content", "").lower() for w in query_words)]

    shown = matches or all_chunks
    if not matches:
        print(f"No chunk matched any word in '{args.query}' - showing all {len(all_chunks)} chunk(s) for this document instead:\n")
    else:
        print(f"{len(matches)} of {len(all_chunks)} chunk(s) matched:\n")

    for chunk in shown:
        print(f"--- section: {chunk.get('section')} (chunk_id: {chunk.get('chunk_id')}) ---")
        print(chunk["content"][:500])
        print()


def cmd_approve(args: argparse.Namespace) -> None:
    db = get_firestore_client()
    approve_document(db, args.document_id, reviewed_by=args.reviewed_by)
    print(f"Approved and enabled '{args.document_id}' for production retrieval.")
    # Sanity check: prove it's now actually retrievable.
    results = search_poultry_knowledge(db, "poultry management", top_k=1)
    print(f"(sanity check: {len(results)} result(s) returned for a generic query post-approval)")


def cmd_disable(args: argparse.Namespace) -> None:
    db = get_firestore_client()
    disable_document(db, args.document_id)
    print(f"Disabled '{args.document_id}' - no longer retrievable, metadata/history preserved.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Chunk and store a new document (disabled/pending until approved)")
    p_ingest.add_argument("--file", required=True)
    p_ingest.add_argument("--metadata", required=True)
    p_ingest.set_defaults(func=cmd_ingest)

    p_test = sub.add_parser("test-retrieval", help="Review a pending document's chunks before approving it")
    p_test.add_argument("--document-id", required=True)
    p_test.add_argument("--query", required=True)
    p_test.set_defaults(func=cmd_test_retrieval)

    p_approve = sub.add_parser("approve", help="Enable a reviewed document for production retrieval")
    p_approve.add_argument("--document-id", required=True)
    p_approve.add_argument("--reviewed-by", required=True)
    p_approve.set_defaults(func=cmd_approve)

    p_disable = sub.add_parser("disable", help="Remove a document from active retrieval (keeps its history)")
    p_disable.add_argument("--document-id", required=True)
    p_disable.set_defaults(func=cmd_disable)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
