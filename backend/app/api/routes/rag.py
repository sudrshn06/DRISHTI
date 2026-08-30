from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user, require_admin
from app.models.user import UserModel
from app.models.rag import RegulatoryKnowledgeChunkModel
from app.services.rag_retrieval_service import generate_grounded_explanation
from app.services.rag_ingestion_service import seed_approved_corpus
from pydantic import BaseModel

router = APIRouter()

class GroundedExplanationRequest(BaseModel):
    query: str
    domain: str
    reference_date: date

class SourceInfo(BaseModel):
    title: str
    provision_number: str
    official_source: str

class GroundedExplanationResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]

class RuleLibraryItem(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    regulatory_domain: str
    provision_number: str
    effective_from: date
    official_source: str
    content: str
    status: str # "Current" | "Future" | "Historical"

@router.post("/explain", response_model=GroundedExplanationResponse, status_code=status.HTTP_200_OK)
def explain_finding(
    req: GroundedExplanationRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Retrieves the applicable regulatory provision and generates a grounded explanation.
    """
    result = generate_grounded_explanation(db, req.query, req.domain, req.reference_date)
    return GroundedExplanationResponse(
        answer=result["answer"],
        sources=[
            SourceInfo(
                title=s["title"],
                provision_number=s["provision_number"],
                official_source=s["official_source"]
            )
            for s in result["sources"]
        ]
    )

@router.get("/rules", response_model=List[RuleLibraryItem], status_code=status.HTTP_200_OK)
def get_rule_library(
    domain: Optional[str] = Query(None, description="Filter by domain: LEGAL_METROLOGY or FOOD_LABEL_FSSAI"),
    search: Optional[str] = Query(None, description="Semantic text search query"),
    reference_date: Optional[date] = Query(None, description="Check rule status as of this reference date"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Enables officers to browse, search, and view official rules/provisions from the library.
    """
    ref_date = reference_date or date.today()
    
    query_builder = db.query(RegulatoryKnowledgeChunkModel)
    if domain:
        query_builder = query_builder.filter(RegulatoryKnowledgeChunkModel.regulatory_domain == domain)
        
    chunks = query_builder.all()
    
    # Filter by search string if present
    if search:
        search_lower = search.lower()
        chunks = [
            c for c in chunks 
            if search_lower in c.content.lower() 
            or search_lower in c.title.lower() 
            or search_lower in c.provision_number.lower()
        ]
        
    library_items = []
    for c in chunks:
        # Determine status dynamically
        rule_status = "Current" if c.effective_from <= ref_date else "Future"
        library_items.append(RuleLibraryItem(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            title=c.title,
            regulatory_domain=c.regulatory_domain,
            provision_number=c.provision_number,
            effective_from=c.effective_from,
            official_source=c.official_source,
            content=c.content,
            status=rule_status
        ))
        
    return library_items

@router.post("/reindex", status_code=status.HTTP_200_OK)
def reindex_corpus(
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(require_admin)
):
    """
    Admin-only endpoint to reindex/reseed the approved official regulatory corpus.
    """
    seeded_count = seed_approved_corpus(db)
    return {"status": "SUCCESS", "seeded_count": seeded_count}
