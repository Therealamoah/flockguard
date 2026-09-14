from datetime import datetime, timezone

import pytest

from app.services.knowledge_service import (
    KnowledgeChunk,
    KnowledgeDocument,
    ReviewStatus,
    SourceType,
    add_chunk,
    add_document,
    approve_document,
    disable_document,
    search_poultry_knowledge,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _make_document(doc_id, *, category="water_management", usage_permission="unknown", review_status=ReviewStatus.PENDING, enabled=False, production_type=None):
    return KnowledgeDocument(
        document_id=doc_id,
        title=f"Title {doc_id}",
        publisher="Test Extension Service",
        category=category,
        production_type=production_type,
        source_type=SourceType.UNIVERSITY_EXTENSION,
        usage_permission=usage_permission,
        review_status=review_status,
        enabled=enabled,
        created_at=_now(),
        updated_at=_now(),
    )


def _make_chunk(chunk_id, document_id, content, *, category="water_management", section=None, page=None, enabled=True):
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        title=f"Title {document_id}",
        publisher="Test Extension Service",
        category=category,
        section=section,
        page=page,
        content=content,
        enabled=enabled,
    )


def test_empty_knowledge_base_returns_empty_list_not_error(fake_db):
    assert search_poultry_knowledge(fake_db, "water availability") == []


def test_pending_document_excluded(fake_db):
    doc = _make_document("d1", usage_permission="approved", review_status=ReviewStatus.PENDING, enabled=False)
    add_document(fake_db, doc)
    add_chunk(fake_db, _make_chunk("c1", "d1", "Check water availability and drinker function daily."))
    assert search_poultry_knowledge(fake_db, "water drinker function") == []


def test_rejected_document_excluded_even_if_enabled_flag_stuck_true(fake_db):
    doc = _make_document("d1", usage_permission="approved", review_status=ReviewStatus.REJECTED, enabled=True)
    add_document(fake_db, doc)
    add_chunk(fake_db, _make_chunk("c1", "d1", "Check water availability and drinker function daily."))
    assert search_poultry_knowledge(fake_db, "water drinker function") == []


def test_missing_usage_permission_excluded(fake_db):
    doc = _make_document("d1", usage_permission="unknown", review_status=ReviewStatus.APPROVED, enabled=True)
    add_document(fake_db, doc)
    add_chunk(fake_db, _make_chunk("c1", "d1", "Check water availability and drinker function daily."))
    assert search_poultry_knowledge(fake_db, "water drinker function") == []


def test_disabled_document_excluded(fake_db):
    doc = _make_document("d1", usage_permission="approved", review_status=ReviewStatus.APPROVED, enabled=True)
    add_document(fake_db, doc)
    add_chunk(fake_db, _make_chunk("c1", "d1", "Check water availability and drinker function daily."))
    disable_document(fake_db, "d1")
    assert search_poultry_knowledge(fake_db, "water drinker function") == []


def test_approved_document_is_retrievable_with_full_attribution(fake_db):
    doc = _make_document("d1", usage_permission="approved", review_status=ReviewStatus.APPROVED, enabled=True)
    add_document(fake_db, doc)
    add_chunk(fake_db, _make_chunk("c1", "d1", "Check water availability and drinker function during inspection.", section="Water Availability", page=12))

    results = search_poultry_knowledge(fake_db, "water availability drinker")
    assert len(results) == 1
    assert results[0]["document_id"] == "d1"
    assert results[0]["title"] == "Title d1"
    assert results[0]["publisher"] == "Test Extension Service"
    assert results[0]["section"] == "Water Availability"
    assert results[0]["page"] == 12
    assert "content" in results[0]
    assert results[0]["relevance_score"] > 0


def test_approve_document_requires_usage_permission_already_approved(fake_db):
    doc = _make_document("d1", usage_permission="unknown", review_status=ReviewStatus.PENDING, enabled=False)
    add_document(fake_db, doc)
    with pytest.raises(ValueError):
        approve_document(fake_db, "d1", reviewed_by="reviewer@example.com")


def test_category_filter(fake_db):
    doc = _make_document("d1", usage_permission="approved", review_status=ReviewStatus.APPROVED, enabled=True)
    add_document(fake_db, doc)
    add_chunk(fake_db, _make_chunk("c1", "d1", "Ventilation reduces ammonia buildup.", category="ventilation"))
    add_chunk(fake_db, _make_chunk("c2", "d1", "Water lines should be flushed weekly.", category="water_management"))

    water_only = search_poultry_knowledge(fake_db, "water ventilation", category="water_management")
    assert [r["document_id"] for r in water_only] == ["d1"]
    assert water_only[0]["content"].startswith("Water lines")


def test_production_type_filter(fake_db):
    broiler_doc = _make_document("d1", usage_permission="approved", review_status=ReviewStatus.APPROVED, enabled=True, production_type="broiler")
    layer_doc = _make_document("d2", usage_permission="approved", review_status=ReviewStatus.APPROVED, enabled=True, production_type="layer")
    add_document(fake_db, broiler_doc)
    add_document(fake_db, layer_doc)
    add_chunk(fake_db, _make_chunk("c1", "d1", "Broiler feed transition guidance for starter to grower."))
    add_chunk(fake_db, _make_chunk("c2", "d2", "Layer feed transition guidance for point of lay."))

    results = search_poultry_knowledge(fake_db, "feed transition guidance", production_type="broiler")
    assert [r["document_id"] for r in results] == ["d1"]


def test_top_k_limits_results(fake_db):
    doc = _make_document("d1", usage_permission="approved", review_status=ReviewStatus.APPROVED, enabled=True)
    add_document(fake_db, doc)
    for i in range(10):
        add_chunk(fake_db, _make_chunk(f"c{i}", "d1", "Water availability and drinker function guidance."))

    results = search_poultry_knowledge(fake_db, "water availability drinker", top_k=3)
    assert len(results) == 3


def test_no_relevant_result_returns_empty_not_lowest_ranked_junk(fake_db):
    doc = _make_document("d1", usage_permission="approved", review_status=ReviewStatus.APPROVED, enabled=True)
    add_document(fake_db, doc)
    add_chunk(fake_db, _make_chunk("c1", "d1", "Biosecurity footbath protocol for visitors."))

    results = search_poultry_knowledge(fake_db, "feed conversion ratio broiler starter")
    assert results == []
