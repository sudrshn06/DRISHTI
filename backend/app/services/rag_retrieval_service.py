import math
from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.rag import RegulatoryKnowledgeChunkModel

def tokenize(text: str) -> List[str]:
    text_lower = text.lower()
    # clean punctuation
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in text_lower)
    return [w for w in cleaned.split() if len(w) > 1]

def retrieve_regulatory_chunks(
    db: Session,
    query: str,
    domain: str,
    reference_date: date,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """
    Retrieves the most semantically relevant chunks filtered by domain and reference_date.
    Uses pure-Python TF-IDF vector matching.
    """
    # Fetch chunks filtered by domain and reference_date
    chunks = db.query(RegulatoryKnowledgeChunkModel).filter(
        RegulatoryKnowledgeChunkModel.regulatory_domain == domain,
        RegulatoryKnowledgeChunkModel.effective_from <= reference_date
    ).all()
    
    if not chunks:
        return []
        
    query_tokens = tokenize(query)
    if not query_tokens:
        return [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "title": c.title,
                "provision_number": c.provision_number,
                "official_source": c.official_source,
                "content": c.content,
                "score": 0.0
            }
            for c in chunks[:top_k]
        ]
        
    N = len(chunks)
    doc_tokens_list = [tokenize(c.content) for c in chunks]
    
    # Calculate Document Frequency
    df: Dict[str, int] = {}
    for doc_tokens in doc_tokens_list:
        seen = set(doc_tokens)
        for term in seen:
            df[term] = df.get(term, 0) + 1
            
    scores: List[float] = []
    for i, chunk in enumerate(chunks):
        doc_tokens = doc_tokens_list[i]
        doc_len = len(doc_tokens)
        if doc_len == 0:
            scores.append(0.0)
            continue
            
        doc_tf: Dict[str, int] = {}
        for term in doc_tokens:
            doc_tf[term] = doc_tf.get(term, 0) + 1
            
        score = 0.0
        query_norm = 0.0
        doc_norm = 0.0
        
        for term in set(query_tokens):
            term_df = df.get(term, 0)
            if term_df == 0:
                continue
            idf = math.log((N + 1) / (term_df + 0.5))
            
            q_tf = query_tokens.count(term)
            q_val = q_tf * idf
            query_norm += q_val * q_val
            
            d_tf = doc_tf.get(term, 0)
            if d_tf > 0:
                d_val = (d_tf / doc_len) * idf
                score += q_val * d_val
                
        if query_norm > 0:
            for term, tf in doc_tf.items():
                term_df = df.get(term, 0)
                idf = math.log((N + 1) / (term_df + 0.5))
                d_val = (tf / doc_len) * idf
                doc_norm += d_val * d_val
                
            if doc_norm > 0:
                score = score / (math.sqrt(query_norm) * math.sqrt(doc_norm))
                
        scores.append(score)
        
    ranked = sorted(
        [
            {
                "chunk_id": chunks[idx].chunk_id,
                "document_id": chunks[idx].document_id,
                "title": chunks[idx].title,
                "provision_number": chunks[idx].provision_number,
                "official_source": chunks[idx].official_source,
                "content": chunks[idx].content,
                "score": scores[idx]
            }
            for idx in range(N)
        ],
        key=lambda x: x["score"],
        reverse=True
    )
    
    return ranked[:top_k]

def generate_grounded_explanation(
    db: Session,
    query: str,
    domain: str,
    reference_date: date
) -> Dict[str, Any]:
    """
    Generates a grounded explanation based on the top retrieved chunk.
    """
    ranked = retrieve_regulatory_chunks(db, query, domain, reference_date, top_k=2)
    
    # Check retrieval confidence (score must be >= 0.05 to avoid hallucination)
    if not ranked or ranked[0]["score"] < 0.05:
        return {
            "answer": "DRISHTI could not locate sufficient authoritative material to answer this reliably.",
            "sources": []
        }
        
    best = ranked[0]
    title = best["title"]
    source = best["official_source"]
    content = best["content"]
    provision = best["provision_number"]
    
    answer = (
        f"According to the official regulation {title} ({source}), it is mandated:\n\n"
        f"\"{content}\"\n\n"
        f"Explanation: Under {provision}, this requirement is active and applicable to the packaging layout. "
        f"Verify that declarations are conspicuous, legible, and conform to the specified statutory metrics."
    )
    
    return {
        "answer": answer,
        "sources": [
            {
                "title": best["title"],
                "provision_number": best["provision_number"],
                "official_source": best["official_source"]
            }
        ]
    }
