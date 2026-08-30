import pytest
from datetime import date
from app.schemas.ocr import FieldCandidate, BusinessNormalized, MrpNormalized, NetQuantityNormalized
from app.schemas.inspection import InspectionSession, CaptureRecord, CapturePlan, CaptureViewRequirement
from app.schemas.applicability import ApplicabilityStatus
from app.schemas.compliance import LegalStatus
from app.services.applicability_model import evaluate_applicability
from app.services.compliance_service import orchestrate_compliance
from app.services.rule_loader import load_production_rules
from app.services.inspection_service import aggregate_candidates
from app.api.routes.inspections import compute_active_clarification, _update_session_compliance

def test_1_and_2_initial_analysis_returns_only_one_progressive_clarification():
    # 1 & 2. Initial analysis does not expose all possible contexts at once; returns single highest-value question
    session = InspectionSession(
        inspection_id="test_sess_1",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        captures=[]
    )
    _update_session_compliance(session)
    
    # Verify required_context has multiple missing contexts, but active_clarification is ONE question
    assert len(session.required_context) > 1
    assert session.active_clarification is not None
    assert session.active_clarification.question_id == "PRODUCT_TYPE"
    assert session.active_clarification.title == "What type of packaged product is this?"
    assert len(session.active_clarification.options) == 5

def test_3_and_4_food_selection_removes_redundant_date_regime_and_recomputes():
    # 3 & 4. Answering FOOD updates context, re-evaluates compliance, and removes redundant date clarification
    session = InspectionSession(
        inspection_id="test_sess_2",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        regulatory_product_class="FOOD",
        date_regulatory_regime="FOOD",
        date_package_exemption="NONE",
        captures=[]
    )
    _update_session_compliance(session)
    
    # Business rules and date rules become NOT_APPLICABLE under food exception
    mfg = next(r for r in session.rule_evaluations if r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE")
    date_r = next(r for r in session.rule_evaluations if r.rule_id == "MONTH_YEAR_DECLARATION_PRESENCE")
    assert mfg.status == LegalStatus.NOT_APPLICABLE
    assert date_r.status == LegalStatus.NOT_APPLICABLE
    
    # DATE_REGULATORY_REGIME is no longer in required_context
    missing_fields = {rc.field for rc in session.required_context}
    assert "DATE_REGULATORY_REGIME" not in missing_fields
    assert "REGULATORY_PRODUCT_CLASS" not in missing_fields
    
    # Next active clarification advances to origin if needed
    if session.active_clarification:
        assert session.active_clarification.question_id != "PRODUCT_TYPE"
        assert session.active_clarification.question_id != "DATE_EXEMPTION"

def test_5_suppress_unrelated_questions_when_cannot_currently_resolve_rule():
    # 5. USP questions (PACKAGE_STRUCTURE / ALCOHOL_CONTEXT) are suppressed when MRP is unresolved
    session = InspectionSession(
        inspection_id="test_sess_3",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        regulatory_product_class="NON_FOOD",
        product_origin="DOMESTIC",
        date_regulatory_regime="GENERAL",
        date_package_exemption="NONE",
        aggregated_candidates=[], # No clean MRP or Net Qty detected
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        captures=[]
    )
    _update_session_compliance(session)
    
    # USP questions must be suppressed because MRP is missing/unresolved
    assert session.active_clarification is None or session.active_clarification.question_id not in ("PACKAGE_STRUCTURE", "ALCOHOL_CONTEXT")
    
    # Electronic question is also suppressed because evidence is insufficient for absence evaluation
    assert session.active_clarification is None or session.active_clarification.question_id != "IS_ELECTRONIC"

def test_6_and_7_every_clarification_has_not_sure_and_preserves_unknown():
    # 6 & 7. Every clarification has a Not sure path which preserves UNKNOWN
    session = InspectionSession(
        inspection_id="test_sess_4",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        captures=[]
    )
    _update_session_compliance(session)
    
    q = session.active_clarification
    assert q is not None
    not_sure_opt = next((o for o in q.options if o.id == "NOT_SURE"), None)
    assert not_sure_opt is not None
    assert not_sure_opt.label == "Not sure"
    
    # Simulate user dismissing with Not sure
    session.dismissed_clarifications.append(q.question_id)
    _update_session_compliance(session)
    
    # Context remains UNKNOWN
    assert session.regulatory_product_class == "UNKNOWN"
    # Clarification moves to next priority or finishes
    if session.active_clarification:
        assert session.active_clarification.question_id != q.question_id

def test_8_clarification_does_not_rerun_ocr():
    # 8. Updating context re-evaluates compliance on existing aggregated candidates directly
    cand = FieldCandidate(field="MRP", status="DETECTED", normalized_value=MrpNormalized(amount=100.0, currency="INR"), evidence_ids=["ev1"])
    session = InspectionSession(
        inspection_id="test_sess_5",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        aggregated_candidates=[cand],
        captures=[]
    )
    _update_session_compliance(session)
    
    # Candidate remains intact and evaluated
    mrp_res = next(r for r in session.rule_evaluations if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_res.status == LegalStatus.PASS

def test_9_and_10_one_capture_conflicts_and_provenance():
    # 9 & 10. Single capture conflicts stay REVIEW_REQUIRED with capture_ids=[cap1]
    c1 = FieldCandidate(field="MRP", status="DETECTED", normalized_value=MrpNormalized(amount=100.0, currency="INR"), evidence_ids=["ev1"])
    c2 = FieldCandidate(field="MRP", status="DETECTED", normalized_value=MrpNormalized(amount=200.0, currency="INR"), evidence_ids=["ev2"])
    
    rec = CaptureRecord(capture_id="cap_front", view_id="FRONT", field_candidates=[c1, c2], status="ACCEPTED", pipeline_status="COMPLETED")
    agg = aggregate_candidates([rec])
    
    mrp = next(c for c in agg if c.field == "MRP")
    assert mrp.status == "REVIEW_REQUIRED"
    assert mrp.capture_ids == ["cap_front"]
    assert len(mrp.capture_ids) == 1 # Proves it is single-capture

def test_11_multi_capture_conflicts_have_multiple_capture_ids():
    # 11. Multi-capture conflicts contain both capture IDs
    c1 = FieldCandidate(field="MRP", status="DETECTED", normalized_value=MrpNormalized(amount=100.0, currency="INR"), evidence_ids=["ev1"])
    c2 = FieldCandidate(field="MRP", status="DETECTED", normalized_value=MrpNormalized(amount=200.0, currency="INR"), evidence_ids=["ev2"])
    
    rec1 = CaptureRecord(capture_id="cap_front", view_id="FRONT", field_candidates=[c1], status="ACCEPTED", pipeline_status="COMPLETED")
    rec2 = CaptureRecord(capture_id="cap_back", view_id="BACK", field_candidates=[c2], status="ACCEPTED", pipeline_status="COMPLETED")
    agg = aggregate_candidates([rec1, rec2])
    
    mrp = next(c for c in agg if c.field == "MRP")
    assert mrp.status == "REVIEW_REQUIRED"
    assert set(mrp.capture_ids) == {"cap_front", "cap_back"}
    assert len(mrp.capture_ids) == 2

def test_12_no_legal_semantics_changed():
    # 12. Legal semantics unchanged
    rules = load_production_rules()
    decisions = evaluate_applicability(
        rules, [], "GENERIC_RETAIL_PACKAGE",
        product_origin="DOMESTIC",
        regulatory_category="NON_FOOD"
    )
    assert decisions["IMPORTER_DECLARATION_PRESENCE"].status == ApplicabilityStatus.NOT_APPLICABLE
    assert decisions["MANUFACTURER_PACKER_DECLARATION_PRESENCE"].status == ApplicabilityStatus.APPLICABLE

