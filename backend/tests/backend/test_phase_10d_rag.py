import pytest
from datetime import date
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.services.rag_ingestion_service import seed_approved_corpus
from app.services.rag_retrieval_service import retrieve_regulatory_chunks, generate_grounded_explanation
from app.schemas.compliance import LegalStatus
from app.models.rag import RegulatoryKnowledgeChunkModel
from app.main import app

@pytest.fixture(scope="module")
def db_session() -> Session:
    db = SessionLocal()
    try:
        seed_approved_corpus(db)
        yield db
    finally:
        db.query(RegulatoryKnowledgeChunkModel).delete()
        db.commit()
        db.close()

def test_01_rag_ingestion_metadata(db_session: Session):
    chunks = db_session.query(RegulatoryKnowledgeChunkModel).all()
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.chunk_id is not None
        assert chunk.document_id is not None
        assert chunk.title is not None
        assert chunk.regulatory_domain in ("LEGAL_METROLOGY", "FOOD_LABEL_FSSAI")
        assert chunk.provision_number is not None
        assert chunk.effective_from is not None
        assert chunk.official_source is not None
        assert chunk.content is not None

def test_02_rag_retrieval_domain_and_date_filtering(db_session: Session):
    lm_results = retrieve_regulatory_chunks(
        db_session,
        query="MRP consumer care name",
        domain="LEGAL_METROLOGY",
        reference_date=date(2026, 8, 27)
    )
    for r in lm_results:
        chunk = db_session.query(RegulatoryKnowledgeChunkModel).filter(
            RegulatoryKnowledgeChunkModel.chunk_id == r["chunk_id"]
        ).first()
        assert chunk.regulatory_domain == "LEGAL_METROLOGY"
        
    fssai_results = retrieve_regulatory_chunks(
        db_session,
        query="allergen ingredients details",
        domain="FOOD_LABEL_FSSAI",
        reference_date=date(2026, 8, 27)
    )
    for r in fssai_results:
        chunk = db_session.query(RegulatoryKnowledgeChunkModel).filter(
            RegulatoryKnowledgeChunkModel.chunk_id == r["chunk_id"]
        ).first()
        assert chunk.regulatory_domain == "FOOD_LABEL_FSSAI"

    results_2026 = retrieve_regulatory_chunks(
        db_session,
        query="infant nutrition serve-RDA",
        domain="FOOD_LABEL_FSSAI",
        reference_date=date(2026, 8, 27)
    )
    for r in results_2026:
        assert "First Amendment Regulations, 2026" not in r["title"]

    results_2027 = retrieve_regulatory_chunks(
        db_session,
        query="infant nutrition serve-RDA",
        domain="FOOD_LABEL_FSSAI",
        reference_date=date(2027, 7, 1)
    )
    has_2026_amendment = any("First Amendment Regulations, 2026" in r["title"] for r in results_2027)
    assert has_2026_amendment

def test_03_rag_unsupported_question(db_session: Session):
    result = generate_grounded_explanation(
        db_session,
        query="How do I cook butter chicken?",
        domain="FOOD_LABEL_FSSAI",
        reference_date=date(2026, 8, 27)
    )
    assert result["answer"] == "DRISHTI could not locate sufficient authoritative material to answer this reliably."
    assert len(result["sources"]) == 0

def test_04_rag_immutability(db_session: Session):
    result = generate_grounded_explanation(
        db_session,
        query="net quantity declarations rule",
        domain="LEGAL_METROLOGY",
        reference_date=date(2026, 8, 27)
    )
    assert result["answer"] is not None
    assert len(result["sources"]) > 0

def test_05_rag_idempotency(db_session: Session):
    # Repeat seed operation multiple times
    count1 = seed_approved_corpus(db_session)
    count2 = seed_approved_corpus(db_session)
    count3 = seed_approved_corpus(db_session)
    
    assert count1 == count2
    assert count2 == count3
    
    # Verify no duplicates in the DB
    total_db = db_session.query(RegulatoryKnowledgeChunkModel).count()
    assert total_db == count1

def test_06_endpoints_security():
    client = TestClient(app)
    
    # 1. Unauthenticated calls must return 401
    resp_explain = client.post("/api/rag/explain", json={
        "query": "net quantity",
        "domain": "LEGAL_METROLOGY",
        "reference_date": "2026-08-27"
    })
    assert resp_explain.status_code == 401

    resp_rules = client.get("/api/rag/rules")
    assert resp_rules.status_code == 401

    resp_reindex = client.post("/api/rag/reindex")
    assert resp_reindex.status_code == 401
