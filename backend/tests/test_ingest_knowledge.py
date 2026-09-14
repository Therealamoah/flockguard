import importlib.util
import sys
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "ingest_knowledge.py"
_spec = importlib.util.spec_from_file_location("ingest_knowledge", _SCRIPT_PATH)
ingest_knowledge = importlib.util.module_from_spec(_spec)
sys.modules["ingest_knowledge"] = ingest_knowledge
_spec.loader.exec_module(ingest_knowledge)


def test_section_aware_chunking_splits_on_headings():
    text = (
        "# Water Management\n\n"
        "Check drinker lines daily.\n\n"
        "Flush weekly.\n\n"
        "## Feed Management\n\n"
        "Store feed in a dry, rodent-proof area."
    )
    chunks = ingest_knowledge._section_aware_chunks(text)
    sections = [title for title, _ in chunks]
    assert "Water Management" in sections
    assert "Feed Management" in sections
    water_chunk = next(content for title, content in chunks if title == "Water Management")
    assert "drinker lines" in water_chunk
    assert "Flush weekly" in water_chunk


def test_chunking_falls_back_to_whole_text_when_no_headings():
    text = "Just a plain paragraph with no markdown structure at all."
    chunks = ingest_knowledge._section_aware_chunks(text)
    assert len(chunks) == 1
    assert chunks[0][0] is None
    assert chunks[0][1] == text


def test_long_section_is_split_at_paragraph_boundaries_not_mid_sentence():
    long_para_a = "Sentence about water access. " * 100  # well over _MAX_CHUNK_CHARS
    long_para_b = "Sentence about feed access. " * 100
    text = f"# Section\n\n{long_para_a}\n\n{long_para_b}"
    chunks = ingest_knowledge._section_aware_chunks(text)
    assert len(chunks) >= 2
    for _, content in chunks:
        assert content.strip().endswith(".")  # never cut mid-sentence


class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_test_retrieval_matches_any_query_word_not_the_whole_phrase(monkeypatch, fake_db, capsys):
    """Regression test: the original implementation required the entire
    query string as one literal substring, which almost never matches a
    real multi-word question against real prose."""
    from app.services.knowledge_service import KnowledgeChunk, add_chunk

    add_chunk(
        fake_db,
        KnowledgeChunk(
            chunk_id="c1",
            document_id="doc-1",
            title="Test Doc",
            category="water_management",
            section="Crop Condition",
            content="Crop condition indicates water availability during transfer.",
        ),
    )
    monkeypatch.setattr(ingest_knowledge, "get_firestore_client", lambda: fake_db)

    ingest_knowledge.cmd_test_retrieval(_Args(document_id="doc-1", query="crop condition water"))
    output = capsys.readouterr().out

    assert "1 of 1 chunk(s) matched" in output
    assert "Crop Condition" in output


def test_test_retrieval_falls_back_to_showing_all_chunks_when_nothing_matches(monkeypatch, fake_db, capsys):
    from app.services.knowledge_service import KnowledgeChunk, add_chunk

    add_chunk(
        fake_db,
        KnowledgeChunk(chunk_id="c1", document_id="doc-1", title="Test Doc", category="water_management", content="Unrelated content."),
    )
    monkeypatch.setattr(ingest_knowledge, "get_firestore_client", lambda: fake_db)

    ingest_knowledge.cmd_test_retrieval(_Args(document_id="doc-1", query="zzz_no_match_zzz"))
    output = capsys.readouterr().out

    assert "showing all 1 chunk(s)" in output
    assert "Unrelated content." in output


def test_test_retrieval_reports_when_document_has_no_chunks(monkeypatch, fake_db, capsys):
    monkeypatch.setattr(ingest_knowledge, "get_firestore_client", lambda: fake_db)

    ingest_knowledge.cmd_test_retrieval(_Args(document_id="never-ingested", query="water"))
    output = capsys.readouterr().out

    assert "No chunks found" in output
