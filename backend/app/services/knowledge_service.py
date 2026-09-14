"""Curated poultry reference knowledge (RAG) - global, not org-scoped;
every organization retrieves from the same approved knowledge base.

CRITICAL: this module is NEVER the source of farm truth. It supplements
an investigation with general reference guidance; it must never be used
to fill in a missing farm measurement (see poultry_safety SKILL.md).

Storage decision: Firestore-backed chunk documents with simple keyword/
term-overlap relevance scoring - NOT a vector database. At the scale this
spec targets (roughly 10-20 curated documents), a dedicated vector store
(Pinecone/Weaviate/Qdrant/FAISS) is unjustified infrastructure: Firestore
already holds every other piece of this app's data and needs zero new
deployment dependencies, and term-overlap scoring is entirely adequate
for ranking a few hundred short chunks. `search_poultry_knowledge`'s
signature is written so this can be swapped for real embeddings later
without changing any caller.

The production knowledge base starts EMPTY. No documents are invented or
faked here - see scripts/ingest_knowledge.py and the ingestion checklist
in the final report for how to add real, approved ones.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum

from google.cloud.firestore import Client
from pydantic import BaseModel

from app.core.refs import knowledge_chunks_ref, knowledge_documents_ref


class SourceType(str, Enum):
    GOVERNMENT = "government"
    UNIVERSITY_EXTENSION = "university_extension"
    BREEDER_MANUAL = "breeder_manual"
    FARM_SOP = "farm_sop"
    EXPERT_REVIEWED = "expert_reviewed"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_UPDATE = "needs_update"


class KnowledgeDocument(BaseModel):
    document_id: str
    title: str
    publisher: str | None = None
    category: str
    species: str = "poultry"
    production_type: str | None = None
    breed: str | None = None
    country_or_region: str | None = None
    publication_date: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_type: SourceType
    license_status: str = "review_required"
    usage_permission: str = "unknown"
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    # Never enabled by default - an operator must explicitly approve a
    # document (see approve_document below) before it's retrievable.
    enabled: bool = False
    created_at: str
    updated_at: str


class KnowledgeChunk(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    publisher: str | None = None
    category: str
    section: str | None = None
    page: int | None = None
    content: str
    source_url: str | None = None
    version: str | None = None
    enabled: bool = True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_document(db: Client, doc: KnowledgeDocument) -> None:
    knowledge_documents_ref(db).document(doc.document_id).set(doc.model_dump(mode="json"))


def add_chunk(db: Client, chunk: KnowledgeChunk) -> None:
    knowledge_chunks_ref(db).document(chunk.chunk_id).set(chunk.model_dump(mode="json"))


def approve_document(db: Client, document_id: str, *, reviewed_by: str) -> None:
    """The only way a document becomes retrievable in production. Requires
    usage_permission to already be explicitly "approved" - reviewing a
    document does not grant it a license it doesn't have."""
    doc_ref = knowledge_documents_ref(db).document(document_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise ValueError(f"Unknown document: {document_id}")
    if snap.to_dict().get("usage_permission") != "approved":
        raise ValueError("usage_permission must be 'approved' before a document can be enabled for retrieval")
    doc_ref.update(
        {
            "review_status": ReviewStatus.APPROVED.value,
            "reviewed_by": reviewed_by,
            "reviewed_at": _now_iso(),
            "enabled": True,
            "updated_at": _now_iso(),
        }
    )


def disable_document(db: Client, document_id: str) -> None:
    """Removes a document from active retrieval without deleting its
    metadata/history - guidance changes over time; old documents should
    be removable without destroying provenance."""
    knowledge_documents_ref(db).document(document_id).update({"enabled": False, "updated_at": _now_iso()})


_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "what", "when", "how", "why", "should", "i", "my",
    "this", "that", "for", "of", "in", "on", "to", "and", "or", "do", "does", "did", "it", "if",
}


def _tokenize(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS}


def _relevance_score(query_tokens: set[str], chunk_text: str) -> float:
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokenize(chunk_text)
    if not chunk_tokens:
        return 0.0
    overlap = query_tokens & chunk_tokens
    return len(overlap) / len(query_tokens)


def search_poultry_knowledge(
    db: Client,
    query: str,
    *,
    category: str | None = None,
    production_type: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Only ever searches chunks belonging to a document that is
    enabled + review_status=approved + usage_permission=approved - an
    unapproved/pending/disabled document is never returned, no matter how
    relevant its content, and an empty knowledge base returns [] rather
    than raising or fabricating a result.
    """
    approved_docs = {}
    for doc_snap in knowledge_documents_ref(db).where("enabled", "==", True).stream():
        data = doc_snap.to_dict()
        if data.get("review_status") != ReviewStatus.APPROVED.value:
            continue
        if data.get("usage_permission") != "approved":
            continue
        if production_type and data.get("production_type") not in (None, production_type):
            continue
        approved_docs[doc_snap.id] = data

    if not approved_docs:
        return []

    query_tokens = _tokenize(query)
    scored: list[tuple[float, dict]] = []
    for chunk_snap in knowledge_chunks_ref(db).where("enabled", "==", True).stream():
        chunk = chunk_snap.to_dict()
        if chunk.get("document_id") not in approved_docs:
            continue
        if category and chunk.get("category") != category:
            continue
        score = _relevance_score(query_tokens, chunk.get("content", ""))
        if score <= 0:
            continue
        scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {
            "content": chunk["content"],
            "document_id": chunk["document_id"],
            "title": chunk.get("title"),
            "publisher": chunk.get("publisher"),
            "category": chunk.get("category"),
            "section": chunk.get("section"),
            "page": chunk.get("page"),
            "source_url": chunk.get("source_url"),
            "relevance_score": round(score, 3),
        }
        for score, chunk in scored[:top_k]
    ]
