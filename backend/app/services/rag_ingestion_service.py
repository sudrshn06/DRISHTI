import uuid
from datetime import date
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.rag import RegulatoryKnowledgeChunkModel

APPROVED_CORPUS: List[Dict[str, Any]] = [
    {
        "chunk_id": "c1611111-1111-1111-1111-111111111111",
        "document_id": "pc_rules_2011",
        "title": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6",
        "regulatory_domain": "LEGAL_METROLOGY",
        "provision_number": "Rule 6",
        "notification_date": date(2011, 3, 7),
        "effective_from": date(2011, 4, 1),
        "official_source": "Ministry of Consumer Affairs Gazette, G.S.R. 202(E)",
        "content": (
            "Rule 6 of the Legal Metrology (Packaged Commodities) Rules, 2011 mandates that every package "
            "shall bear declarations including: common or generic name of the commodity, net quantity, "
            "month and year in which the commodity is pre-packed, retail sale price (MRP), and consumer care "
            "details (name, address, email, telephone of the person/office)."
        )
    },
    {
        "chunk_id": "c1622222-2222-2222-2222-222222222222",
        "document_id": "pc_rules_2011",
        "title": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 8",
        "regulatory_domain": "LEGAL_METROLOGY",
        "provision_number": "Rule 8",
        "notification_date": date(2011, 3, 7),
        "effective_from": date(2011, 4, 1),
        "official_source": "Ministry of Consumer Affairs Gazette, G.S.R. 202(E)",
        "content": (
            "Rule 8 mandates that all declarations on pre-packaged commodities shall be conspicuous, legible, "
            "and prominent. The font size of declarations must meet minimum height thresholds depending on net quantity "
            "(e.g., minimum 1 mm to 8 mm depending on packaging surface area and shape)."
        )
    },
    {
        "chunk_id": "c1633333-3333-3333-3333-333333333333",
        "document_id": "pc_rules_2011",
        "title": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 9",
        "regulatory_domain": "LEGAL_METROLOGY",
        "provision_number": "Rule 9",
        "notification_date": date(2011, 3, 7),
        "effective_from": date(2011, 4, 1),
        "official_source": "Ministry of Consumer Affairs Gazette, G.S.R. 202(E)",
        "content": (
            "Rule 9 requires declarations to be grouped together and placed on the principal display panel (PDP) "
            "of the package. It ensures that consumers can easily read vital statutory information in a single viewing area."
        )
    },
    {
        "chunk_id": "c1644444-4444-4444-4444-444444444444",
        "document_id": "lm_act_2009",
        "title": "Legal Metrology Act, 2009 - Section 36",
        "regulatory_domain": "LEGAL_METROLOGY",
        "provision_number": "Section 36",
        "notification_date": date(2009, 1, 13),
        "effective_from": date(2011, 3, 1),
        "official_source": "Gazette of India",
        "content": (
            "Section 36 of the Legal Metrology Act, 2009 prescribes penalties for manufacturing, packing, importing, "
            "selling, distributing, or delivering pre-packaged commodities that do not conform to the declarations "
            "on the package. Violations can attract fines up to twenty-five thousand rupees for the first offence, "
            "fifty thousand for the second, and imprisonment or larger fines for subsequent offences."
        )
    },
    {
        "chunk_id": "c1655555-5555-5555-5555-555555555555",
        "document_id": "fssai_labelling_2020",
        "title": "FSS (Labelling and Display) Regulations, 2020 - Regulation 5(2)",
        "regulatory_domain": "FOOD_LABEL_FSSAI",
        "provision_number": "Regulation 5(2)",
        "notification_date": date(2020, 11, 17),
        "effective_from": date(2021, 11, 17),
        "official_source": "Food Safety and Standards Gazette",
        "content": (
            "Regulation 5(2) requires a complete list of ingredients to be declared on the label of packaged foods, "
            "in descending order of their starting weight or volume. Single-ingredient foods are exempt under Regulation 5(2)(i)."
        )
    },
    {
        "chunk_id": "c1666666-6666-6666-6666-666666666666",
        "document_id": "fssai_labelling_2020",
        "title": "FSS (Labelling and Display) Regulations, 2020 - Regulation 5(3)",
        "regulatory_domain": "FOOD_LABEL_FSSAI",
        "provision_number": "Regulation 5(3)",
        "notification_date": date(2020, 11, 17),
        "effective_from": date(2021, 11, 17),
        "official_source": "Food Safety and Standards Gazette",
        "content": (
            "Regulation 5(3) mandates nutritional information declarations per 100g or 100ml or per serving on the label. "
            "Exemptions apply under Regulation 5(3)(b) for raw agricultural commodities, single-ingredient products (like sugar, salt), "
            "tea, coffee, and packages with label surface area less than 100 cm²."
        )
    },
    {
        "chunk_id": "c1677777-7777-7777-7777-777777777777",
        "document_id": "fssai_labelling_2020",
        "title": "FSS (Labelling and Display) Regulations, 2020 - Regulation 5(4)",
        "regulatory_domain": "FOOD_LABEL_FSSAI",
        "provision_number": "Regulation 5(4)",
        "notification_date": date(2020, 11, 17),
        "effective_from": date(2021, 11, 17),
        "official_source": "Food Safety and Standards Gazette",
        "content": (
            "Regulation 5(4) requires every package of food to bear a color-coded symbol indicating whether the product is "
            "vegetarian (green circle inside a square) or non-vegetarian (brown triangle inside a square). Exclusions apply to "
            "liquid milk, carbonated water, etc."
        )
    },
    {
        "chunk_id": "c1688888-8888-8888-8888-888888888888",
        "document_id": "fssai_labelling_2020",
        "title": "FSS (Labelling and Display) Regulations, 2020 - Regulation 5(7)",
        "regulatory_domain": "FOOD_LABEL_FSSAI",
        "provision_number": "Regulation 5(7)",
        "notification_date": date(2020, 11, 17),
        "effective_from": date(2021, 11, 17),
        "official_source": "Food Safety and Standards Gazette",
        "content": (
            "Regulation 5(7) mandates the display of the FSSAI logo along with the 14-digit registration or licence number "
            "on the label of all pre-packaged food products."
        )
    },
    {
        "chunk_id": "c1699999-9999-9999-9999-999999999999",
        "document_id": "fssai_labelling_2020",
        "title": "FSS (Labelling and Display) Regulations, 2020 - Regulation 5(14)",
        "regulatory_domain": "FOOD_LABEL_FSSAI",
        "provision_number": "Regulation 5(14)",
        "notification_date": date(2020, 11, 17),
        "effective_from": date(2021, 11, 17),
        "official_source": "Food Safety and Standards Gazette",
        "content": (
            "Regulation 5(14) mandates warnings for allergenic ingredients (e.g. contains milk, wheat, nuts) to be declared "
            "on the label when present in the product."
        )
    },
    {
        "chunk_id": "c1700000-0000-0000-0000-000000000000",
        "document_id": "fssai_amendment_2025",
        "title": "FSS (Labelling and Display) First Amendment Regulations, 2025",
        "regulatory_domain": "FOOD_LABEL_FSSAI",
        "provision_number": "First Amendment, 2025",
        "notification_date": date(2025, 8, 8),
        "effective_from": date(2026, 7, 1),
        "official_source": "FSSAI Gazette F. No. Std/SP-08/A-1.2024-Part(1)",
        "content": (
            "The First Amendment, 2025 introduces strict labelling rules for Coffee-Chicory Mixtures, requiring front-of-pack "
            "Box-layout declarations indicating exact percentages of Coffee and Chicory (in abeyance until 2027-07-01 via FSSAI "
            "Enforcement Direction dated 22 July 2026, which allows interim text declarations)."
        )
    },
    {
        "chunk_id": "c1711111-1111-1111-1111-111111111111",
        "document_id": "fssai_amendment_2026",
        "title": "FSS (Labelling and Display) First Amendment Regulations, 2026",
        "regulatory_domain": "FOOD_LABEL_FSSAI",
        "provision_number": "First Amendment, 2026",
        "notification_date": date(2026, 3, 24),
        "effective_from": date(2027, 7, 1),
        "official_source": "FSSAI Gazette Notification F. No. RAG-2026-01",
        "content": (
            "The First Amendment, 2026 amends Regulation 5(3) with updates on serving size, per-serve RDA and serving information "
            "for infant nutrition, nutritional information exemptions for minimally processed and single-ingredient foods, "
            "and small-package logo treatment."
        )
    }
]

def seed_approved_corpus(db: Session) -> int:
    """
    Clears and seeds the database with the approved corpus list.
    Returns the count of seeded entries.
    """
    db.query(RegulatoryKnowledgeChunkModel).delete()
    
    seeded_count = 0
    for entry in APPROVED_CORPUS:
        chunk = RegulatoryKnowledgeChunkModel(
            chunk_id=entry["chunk_id"],
            document_id=entry["document_id"],
            title=entry["title"],
            regulatory_domain=entry["regulatory_domain"],
            provision_number=entry["provision_number"],
            notification_date=entry["notification_date"],
            effective_from=entry["effective_from"],
            official_source=entry["official_source"],
            content=entry["content"]
        )
        db.add(chunk)
        seeded_count += 1
        
    db.commit()
    return seeded_count
