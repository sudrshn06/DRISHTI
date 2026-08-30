import uuid
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

from app.schemas.inspection import InspectionSession, CapturePlan, CaptureRecord
from app.schemas.compliance import LegalStatus
from app.schemas.report import (
    OverallDisposition,
    ReportMetadata,
    CaptureViewSummary,
    CaptureSummary,
    DeclarationFindingItem,
    VisualComplianceFindingItem,
    ExtractedEvidenceItem,
    ReportEvidenceAsset,
    InspectorContextSnapshot,
    ReportSummaryCounts,
    InspectionReportSnapshot
)

def compute_overall_disposition(
    statutory_findings: List[DeclarationFindingItem],
    visual_findings: List[VisualComplianceFindingItem],
    capture_status: str,
    evidence_sufficiency: str
) -> Tuple[OverallDisposition, str]:
    """
    Computes a conservative, defensible overall report disposition without arbitrary scores.
    Precedence:
    1. Statutory violations detected -> VIOLATIONS_FOUND
    2. Incomplete required capture workflow -> INCOMPLETE_INSPECTION
    3. Items requiring inspector review -> REVIEW_REQUIRED
    4. Complete scope with 0 violations and 0 review items -> NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE
    """
    # 1. Any statutory FAIL takes top precedence
    fail_items = [f for f in statutory_findings if f.status == "FAIL"]
    if fail_items:
        failed_names = ", ".join(f.rule_id for f in fail_items)
        return (
            OverallDisposition.VIOLATIONS_FOUND,
            f"Statutory violations detected: {failed_names} failed Legal Metrology compliance checks."
        )

    # 2. Report workflow completeness follows the authoritative required-view
    # capture state. Evidence sufficiency remains recorded separately and still
    # governs absence evaluation; it must not make missing optional views look
    # like an incomplete inspection.
    if capture_status != "COMPLETE_EVIDENCE_CAPTURE":
        return (
            OverallDisposition.INCOMPLETE_INSPECTION,
            "Package surface capture is incomplete. Missing declarations cannot be definitively evaluated for absence until all required views are captured."
        )

    # 3. Review required (statutory or visual review required)
    statutory_reviews = [f for f in statutory_findings if f.status == "REVIEW_REQUIRED"]
    visual_reviews = [f for f in visual_findings if f.status in ("REVIEW_REQUIRED", "NEEDS_RECAPTURE")]
    
    if statutory_reviews or visual_reviews:
        reasons = []
        if statutory_reviews:
            reasons.append(f"{len(statutory_reviews)} statutory declaration check(s) require inspector review")
        if visual_reviews:
            reasons.append(f"{len(visual_reviews)} visual observation(s) require inspector verification")
        return (
            OverallDisposition.REVIEW_REQUIRED,
            f"Inspection completed with items requiring review: {'; '.join(reasons)}."
        )

    # 4. Scope fully evaluated without violations
    return (
        OverallDisposition.NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE,
        "All applicable statutory declarations were detected and verified across the complete evaluated scope. No violations were detected."
    )


FSSAI_2026_REGULATORY_NOTE = (
    "First Amendment Regulations, 2026 is not yet effective - notified "
    "2026-03-24, effective 2027-07-01; covers infant nutrition serve-RDA, "
    "small package logo, nutritional exemptions"
)


def resolve_report_disposition(
    report: InspectionReportSnapshot,
) -> Tuple[OverallDisposition, str]:
    """Return the current presentation mapping without mutating a snapshot."""
    return compute_overall_disposition(
        statutory_findings=list(report.declaration_findings) + list(report.food_label_findings),
        visual_findings=list(report.visual_compliance_findings),
        capture_status=report.capture_summary.capture_status,
        evidence_sufficiency=report.capture_summary.evidence_sufficiency,
    )


def present_finding_reason(
    finding: DeclarationFindingItem,
    inspector_context: Optional[InspectorContextSnapshot] = None,
) -> str:
    """Clarify report wording while preserving the finding and its status."""
    reason = finding.reason or ""

    if finding.rule_id == "COUNTRY_OF_ORIGIN_DECLARATION_PRESENCE":
        origin = _display_enum(inspector_context.product_origin) if inspector_context else "Unknown"
        return (
            "No explicit country-of-origin declaration was detected in the package evidence. "
            f"This rule result uses the officer-provided product-origin classification: {origin}."
        )

    if "Supporting text 'None' was detected" in reason:
        reason = (
            "No reliable visual veg/non-veg symbol evidence was detected in the supplied "
            "photographs. Officer verification is required where applicable."
        )

    reason = reason.replace(
        "Corresponding FSSAI evaluation is not implemented yet.",
        "FSSAI business-name/address compliance evaluation is not currently automated.",
    )

    # The shared amendment/version note is rendered once below the FSSAI table.
    return re.sub(
        rf"\s*\({re.escape(FSSAI_2026_REGULATORY_NOTE)}\)\s*$",
        "",
        reason,
    ).strip()


def _display_enum(value: Optional[str]) -> str:
    if not value or value == "UNKNOWN":
        return "Unknown / not established"
    return value.replace("_", " ").title()


def resolve_evidence_asset(
    report: InspectionReportSnapshot,
    evidence: ExtractedEvidenceItem,
) -> Tuple[Optional[ReportEvidenceAsset], bool, bool]:
    """
    Resolve the source asset for a final reconciled candidate.

    Returns (asset, exact_region_supported, use_polygons). A capture-only match is
    contextual evidence and must never receive an invented bounding box.
    """
    evidence_ids = set(evidence.evidence_ids or [])
    evidence_matches = [
        asset
        for asset in report.evidence_assets
        if evidence_ids.intersection(asset.evidence_ids or [])
    ]
    if evidence_matches:
        # Report generation records the final geometry encountered for legacy
        # multi-capture candidates. Selecting the final matched asset preserves
        # that geometry/source association; polygons are safe only for a single
        # matched source image.
        asset = evidence_matches[-1]
        has_geometry = bool(
            evidence.has_geometry
            and (evidence.pixel_box or evidence.normalized_box or evidence.polygons)
        )
        return asset, has_geometry, has_geometry and len(evidence_matches) == 1

    capture_matches = [
        asset
        for asset in report.evidence_assets
        if asset.capture_id in (evidence.capture_ids or [])
    ]
    if capture_matches:
        return capture_matches[0], False, False

    return None, False, False

def generate_inspection_report(
    session: InspectionSession,
    capture_plan: Optional[CapturePlan] = None
) -> InspectionReportSnapshot:
    """
    Generates an immutable structured report snapshot from the current inspection session state.
    """
    report_id = str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat()
    
    # 1. Capture summary & View breakdown
    views_summary: List[CaptureViewSummary] = []
    missing_required: List[str] = []
    total_required = 0
    captured_required = 0
    
    plan_views = capture_plan.views if capture_plan else []
    
    for v_req in plan_views:
        if v_req.required:
            total_required += 1
            
        matching_captures = [c for c in session.captures if c.view_id == v_req.view_id]
        latest_capture: Optional[CaptureRecord] = matching_captures[-1] if matching_captures else None
        
        is_captured = latest_capture is not None
        if v_req.required:
            if is_captured:
                captured_required += 1
            else:
                missing_required.append(v_req.view_id)
                
        views_summary.append(CaptureViewSummary(
            view_id=v_req.view_id,
            display_name=v_req.display_name,
            required=v_req.required,
            captured=is_captured,
            capture_id=latest_capture.capture_id if latest_capture else None,
            quality_status=latest_capture.quality_assessment.quality_status if (latest_capture and latest_capture.quality_assessment) else None,
            reasons=latest_capture.quality_assessment.reasons if (latest_capture and latest_capture.quality_assessment) else [],
            image_sha256=latest_capture.image_sha256 if latest_capture else None
        ))
        
    overall_quality = "ACCEPTABLE"
    if any(c.quality_assessment and c.quality_assessment.quality_status == "RETAKE_RECOMMENDED" for c in session.captures):
        overall_quality = "RETAKE_RECOMMENDED"
        
    capture_summary = CaptureSummary(
        views=views_summary,
        total_views_required=total_required,
        captured_required_count=captured_required,
        missing_required_views=missing_required,
        capture_status=session.capture_status,
        evidence_sufficiency=session.evidence_sufficiency,
        overall_quality_status=overall_quality
    )

    # 2. Statutory Declaration Findings
    declaration_findings: List[DeclarationFindingItem] = []
    for r in (session.rule_evaluations or []):
        legal_ref = getattr(r, "source_reference", None) or getattr(r, "legal_reference", None) or "Legal Metrology (Packaged Commodities) Rules, 2011"
        ev_ids = list(getattr(r, "evidence_ids", None) or getattr(r, "evidence_used", None) or [])
        cap_ids = list(getattr(r, "capture_ids", None) or [])
        
        app_status = "APPLICABLE"
        app_reason = None
        if getattr(r, "applicability", None):
            if hasattr(r.applicability.status, "value"):
                app_status = r.applicability.status.value
            else:
                app_status = str(r.applicability.status)
            app_reason = getattr(r.applicability, "reason", None)
            
        declaration_findings.append(DeclarationFindingItem(
            rule_id=r.rule_id,
            field=r.field,
            status=r.status.value if isinstance(r.status, LegalStatus) else str(r.status),
            reason=r.reason,
            legal_reference=legal_ref,
            applicability_status=app_status,
            applicability_reason=app_reason,
            evidence_ids=ev_ids,
            capture_ids=cap_ids
        ))
        
    # 2b. Food Label Findings (FSSAI)
    food_label_findings: List[DeclarationFindingItem] = []
    for r in (session.food_label_evaluations or []):
        legal_ref = getattr(r, "source_reference", None) or getattr(r, "legal_reference", None) or "Food Safety and Standards (Labelling and Display) Regulations, 2020"
        ev_ids = list(getattr(r, "evidence_ids", None) or getattr(r, "evidence_used", None) or [])
        cap_ids = list(getattr(r, "capture_ids", None) or [])
        
        app_status = "APPLICABLE"
        app_reason = None
        if getattr(r, "applicability", None):
            if hasattr(r.applicability.status, "value"):
                app_status = r.applicability.status.value
            else:
                app_status = str(r.applicability.status)
            app_reason = getattr(r.applicability, "reason", None)
            
        food_label_findings.append(DeclarationFindingItem(
            rule_id=r.rule_id,
            field=r.field,
            status=r.status.value if isinstance(r.status, LegalStatus) else str(r.status),
            reason=r.reason,
            legal_reference=legal_ref,
            applicability_status=app_status,
            applicability_reason=app_reason,
            evidence_ids=ev_ids,
            capture_ids=cap_ids
        ))

    # 3. Visual Compliance Findings
    visual_compliance_findings: List[VisualComplianceFindingItem] = []
    for vr in (session.visual_rule_evaluations or []):
        visual_compliance_findings.append(VisualComplianceFindingItem(
            rule_id=vr.rule_id,
            field=vr.field,
            capability=vr.capability.value if hasattr(vr.capability, "value") else str(vr.capability),
            status=vr.status.value if hasattr(vr.status, "value") else str(vr.status),
            reason=vr.reason,
            legal_reference=vr.legal_reference,
            limitations=str(vr.limitations or ""),
            evidence_ids=list(vr.evidence_ids or []),
            capture_ids=list(vr.capture_ids or [])
        ))

    # 4. Extracted Evidence
    extracted_evidence: List[ExtractedEvidenceItem] = []
    for cand in session.aggregated_candidates:
        cand_ev_ids = list(cand.evidence_ids or [])
        cand_capture_ids = list(cand.capture_ids or [])
        
        # Determine view IDs and geometry from captures
        cand_views = []
        has_geom = False
        pixel_box_dict = None
        norm_box_dict = None
        cand_polygons = []
        geometry_matches = []
        
        for cap in session.captures:
            if cand_capture_ids and cap.capture_id in cand_capture_ids:
                cand_views.append(cap.view_id)
            elif any(ev in cand_ev_ids for ev in (cap.evidence_id or [])):
                cand_views.append(cap.view_id)
                
            assessments = cap.visual_assessment.assessments if cap.visual_assessment else []
            for a in assessments:
                if a.evidence_ids and any(ev in cand_ev_ids for ev in a.evidence_ids):
                    if cap.view_id not in cand_views:
                        cand_views.append(cap.view_id)
                    if a.geometry:
                        geometry_matches.append((a.geometry, list(getattr(a, "polygons", None) or [])))

        # Geometry must come from one source capture. Combining polygons from
        # different photographs creates unrelated report crops even though the
        # final reconciled value itself is correct.
        if geometry_matches:
            selected_geometry, selected_polygons = geometry_matches[-1]
            has_geom = True
            pixel_box_dict = {
                "x_min": selected_geometry.pixel_box.x_min,
                "y_min": selected_geometry.pixel_box.y_min,
                "x_max": selected_geometry.pixel_box.x_max,
                "y_max": selected_geometry.pixel_box.y_max,
                "width_px": selected_geometry.pixel_box.width_px,
                "height_px": selected_geometry.pixel_box.height_px,
            }
            norm_box_dict = {
                "x_min": selected_geometry.normalized_box.x_min,
                "y_min": selected_geometry.normalized_box.y_min,
                "x_max": selected_geometry.normalized_box.x_max,
                "y_max": selected_geometry.normalized_box.y_max,
            }
            cand_polygons = selected_polygons
                        
        norm_val_dict = cand.normalized_value.model_dump() if hasattr(cand.normalized_value, "model_dump") else (cand.normalized_value if isinstance(cand.normalized_value, dict) else None)
        
        extracted_evidence.append(ExtractedEvidenceItem(
            field=cand.field,
            status=cand.status,
            raw_value=cand.raw_value,
            normalized_value=norm_val_dict,
            confidence=cand.confidence,
            evidence_ids=cand_ev_ids,
            capture_ids=cand_capture_ids,
            view_ids=list(dict.fromkeys(cand_views)),
            has_geometry=has_geom,
            pixel_box=pixel_box_dict,
            normalized_box=norm_box_dict,
            polygons=cand_polygons
        ))

    # 5. Report Evidence Assets
    from app.services.image_store import get_capture_image, get_image_by_hash
    import base64

    evidence_assets: List[ReportEvidenceAsset] = []
    for cap in session.captures:
        if cap.image_sha256:
            cap_w = cap.visual_assessment.image_width if (cap.visual_assessment and hasattr(cap.visual_assessment, "image_width")) else None
            cap_h = cap.visual_assessment.image_height if (cap.visual_assessment and hasattr(cap.visual_assessment, "image_height")) else None
            cap_ev_ids = [cap.evidence_id] if cap.evidence_id else []
            if cap.visual_assessment and cap.visual_assessment.assessments:
                for a in cap.visual_assessment.assessments:
                    if a.evidence_ids:
                        cap_ev_ids.extend(a.evidence_ids)

            raw_img = get_capture_image(cap.capture_id) or get_image_by_hash(cap.image_sha256)
            img_b64_str = base64.b64encode(raw_img).decode("ascii") if raw_img else None
                        
            evidence_assets.append(ReportEvidenceAsset(
                capture_id=cap.capture_id,
                view_id=cap.view_id,
                image_sha256=cap.image_sha256,
                media_type="image/jpeg",
                image_width=cap_w,
                image_height=cap_h,
                evidence_ids=list(dict.fromkeys(cap_ev_ids)),
                image_b64=img_b64_str
            ))

    # 6. Inspector Context Snapshot
    inspector_context = InspectorContextSnapshot(
        product_origin=session.product_origin,
        regulatory_product_class=session.regulatory_product_class,
        date_regulatory_regime=session.date_regulatory_regime,
        date_package_exemption=session.date_package_exemption,
        is_electronic=session.is_electronic,
        package_structure=session.package_structure,
        alcohol_context=session.alcohol_context
    )

    # 7. Report Summary Counts
    all_statutory = declaration_findings + food_label_findings
    summary_counts = ReportSummaryCounts(
        total_statutory_checks=len(all_statutory),
        statutory_pass_count=sum(1 for f in all_statutory if f.status == "PASS"),
        statutory_fail_count=sum(1 for f in all_statutory if f.status == "FAIL"),
        statutory_review_required_count=sum(1 for f in all_statutory if f.status == "REVIEW_REQUIRED"),
        statutory_not_applicable_count=sum(1 for f in all_statutory if f.status == "NOT_APPLICABLE"),
        total_visual_checks=len(visual_compliance_findings),
        visual_review_required_count=sum(1 for f in visual_compliance_findings if f.status in ("REVIEW_REQUIRED", "NEEDS_RECAPTURE")),
        visual_not_evaluable_count=sum(1 for f in visual_compliance_findings if f.status == "NOT_EVALUABLE"),
        visual_observation_clear_count=sum(1 for f in visual_compliance_findings if f.status == "OBSERVATION_CLEAR")
    )

    # 8. Overall Disposition
    overall_disposition, disposition_reason = compute_overall_disposition(
        statutory_findings=all_statutory,
        visual_findings=visual_compliance_findings,
        capture_status=session.capture_status,
        evidence_sufficiency=session.evidence_sufficiency
    )

    # 9. Report Metadata
    metadata = ReportMetadata(
        report_id=report_id,
        inspection_id=session.inspection_id,
        report_schema_version="1.0",
        generated_at=generated_at,
        reference_date=session.reference_date,
        product_category=session.product_category,
        capture_plan_id=session.capture_plan_id,
        capture_plan_name=capture_plan.name if capture_plan else None
    )

    return InspectionReportSnapshot(
        metadata=metadata,
        overall_disposition=overall_disposition,
        disposition_reason=disposition_reason,
        summary_counts=summary_counts,
        inspector_context=inspector_context,
        capture_summary=capture_summary,
        declaration_findings=declaration_findings,
        food_label_findings=food_label_findings,
        visual_compliance_findings=visual_compliance_findings,
        extracted_evidence=extracted_evidence,
        evidence_assets=evidence_assets
    )
