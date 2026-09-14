from fastapi import APIRouter, File, UploadFile, Depends, Form, HTTPException, Response, Query, status
from typing import Optional, List, Dict
import uuid
import base64
import hashlib
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.inspection_repository import InspectionRepository
from app.services.storage_adapter import default_storage_adapter
from app.schemas.inspection import (
    CapturePlan, CaptureViewRequirement, CaptureRecord, InspectionSession, RequiredContext,
    ClarificationQuestion, ClarificationOption
)
from app.schemas.ocr import EvidenceItem
from collections import defaultdict
from app.services.image_validator import validate_and_decode_image
from app.services.ocr_engine import analyze_image
from app.services.candidate_extractor import extract_candidates
from app.services.image_quality import assess_image_quality
from app.services.visual_assessment_service import assess_capture_visuals, evaluate_visual_legal_rules
from app.services.inspection_service import evaluate_completeness, aggregate_candidates, evaluate_evidence_sufficiency
from app.services.contextual_vision_service import default_contextual_vision_service
from app.services.gemini_observation_service import refresh_detected_package_context
from app.services.hybrid_reconciliation_service import reconcile_capture_candidates
from app.schemas.officer_review import DeclarationCorrectionRequest
from app.services.officer_review_service import (
    confirm_package_information_review,
    create_officer_declaration_override,
    invalidate_package_information_review,
    package_information_review_is_current,
    rebuild_authoritative_candidates,
)
from app.services.compliance_service import orchestrate_compliance
from app.schemas.report import InspectionReportSnapshot
from app.services.report_service import generate_inspection_report
from app.services.evidence_package_service import build_evidence_manifest, has_confirmed_deterministic_fail
from app.services.pdf_report_service import generate_pdf_report
from app.services.docx_report_service import generate_docx_report
from app.services.image_store import store_capture_image
from app.schemas.workflow import WorkflowSummary
from app.services.workflow_service import WorkflowService
from app.schemas.history import PaginatedInspectionHistory, RelatedInspectionReference
from app.services.history_reference_service import inspection_identity, related_match_basis
import zipfile
import io
import json
from app.schemas.case import CaseExportRequest
from app.services.reproducibility_service import (
    build_reproducibility_record,
    default_capture_processing_provenance,
)

router = APIRouter()

# Active in-memory session cache synchronized with PostgreSQL
_inspections: Dict[str, InspectionSession] = {}

# Prototype Capture Plan
_default_plan = CapturePlan(
    capture_plan_id="plan_software_1",
    name="Standard Software Inspection",
    views=[
        CaptureViewRequirement(view_id="FRONT", display_name="Front", required=True),
        CaptureViewRequirement(view_id="BACK", display_name="Back", required=True),
        CaptureViewRequirement(view_id="SIDE_LEFT", display_name="Side Left", required=False),
        CaptureViewRequirement(view_id="SIDE_RIGHT", display_name="Side Right", required=False),
        CaptureViewRequirement(view_id="TOP", display_name="Top", required=False),
        CaptureViewRequirement(view_id="BOTTOM", display_name="Bottom", required=False),
    ],
    absence_evaluation_eligible=False
)
_capture_plans: Dict[str, CapturePlan] = {
    _default_plan.capture_plan_id: _default_plan
}

def _get_or_load_session(inspection_id: str, db: Optional[Session] = None) -> InspectionSession:
    if inspection_id in _inspections:
        return _inspections[inspection_id]
    
    if db:
        model = InspectionRepository.get_inspection(db, inspection_id)
        if model:
            session = InspectionRepository.inspection_model_to_domain(model)
            if session.package_information_review and not package_information_review_is_current(session):
                invalidate_package_information_review(session)
                InspectionRepository.update_inspection_state(db, session)
            refresh_detected_package_context(session)
            _update_session_compliance(session)
            _inspections[inspection_id] = session
            return session
            
    raise HTTPException(status_code=404, detail="Inspection not found")


def _retrieve_capture_bytes(
    inspection_id: str,
    capture: CaptureRecord,
) -> Optional[bytes]:
    """Resolve current and legacy server-side keys without exposing storage access."""
    candidate_keys = [
        capture.object_key,
        f"inspections/{inspection_id}/captures/{capture.capture_id}/source",
        f"inspections/{inspection_id}/captures/{capture.capture_id}/source.jpg",
        capture.capture_id,
    ]
    tried: set[str] = set()
    for key in candidate_keys:
        if not key or key in tried:
            continue
        tried.add(key)
        try:
            image_bytes = default_storage_adapter.retrieve(key)
        except Exception:
            image_bytes = None
        if image_bytes:
            return image_bytes

    if capture.image_sha256:
        try:
            return default_storage_adapter.retrieve_by_hash(capture.image_sha256)
        except Exception:
            return None
    return None


def _hydrate_report_evidence_assets(report_snapshot: InspectionReportSnapshot, inspection_id: str) -> None:
    """
    Transiently hydrates image_b64 in ReportEvidenceAsset from MinIO/object storage
    with strict SHA-256 cryptographic verification.
    """
    if not report_snapshot.evidence_assets:
        return

    for asset in report_snapshot.evidence_assets:
        if getattr(asset, "image_b64", None) is None:
            session = _inspections.get(inspection_id)
            capture = next(
                (
                    item
                    for item in (session.captures if session else [])
                    if item.capture_id == asset.capture_id
                ),
                None,
            )
            if capture:
                img_bytes = _retrieve_capture_bytes(inspection_id, capture)
            else:
                fallback_capture = CaptureRecord(
                    capture_id=asset.capture_id,
                    view_id=asset.view_id,
                    image_sha256=asset.image_sha256,
                    media_type=asset.media_type,
                )
                img_bytes = _retrieve_capture_bytes(inspection_id, fallback_capture)
                
            if img_bytes:
                # Strict SHA-256 verification
                actual_hash = hashlib.sha256(img_bytes).hexdigest()
                if actual_hash == asset.image_sha256:
                    asset.image_b64 = base64.b64encode(img_bytes).decode("ascii")
                else:
                    asset.image_b64 = None

from app.models.user import UserModel
from app.api.deps import get_authorized_inspection, get_current_user_optional, get_current_user

@router.get("", response_model=PaginatedInspectionHistory)
async def list_inspections(
    page: int = Query(1, ge=1, description="1-indexed page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    search: Optional[str] = Query(None, description="Search term for inspection ID or product category"),
    lifecycle_status: Optional[str] = Query(None, description="Lifecycle status filter"),
    disposition: Optional[str] = Query(None, description="Overall report disposition filter"),
    date_from: Optional[str] = Query(None, description="Creation date from (YYYY-MM-DD or ISO 8601)"),
    date_to: Optional[str] = Query(None, description="Creation date to (YYYY-MM-DD or ISO 8601)"),
    sort: str = Query("newest", description="Sort order: newest, oldest, recently_updated"),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves paginated inspection summaries with searching, filtering, and deterministic sorting.
    Inspectors list strictly their own cases; Admins list across all users.
    """
    VALID_LIFECYCLES = {"DRAFT", "IN_PROGRESS", "READY_FOR_REVIEW", "FINALIZED"}
    if lifecycle_status and lifecycle_status not in VALID_LIFECYCLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lifecycle_status: '{lifecycle_status}'. Allowed values: {sorted(VALID_LIFECYCLES)}"
        )

    VALID_DISPOSITIONS = {
        "VIOLATIONS_FOUND",
        "INCOMPLETE_INSPECTION",
        "REVIEW_REQUIRED",
        "NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE"
    }
    if disposition and disposition not in VALID_DISPOSITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid disposition: '{disposition}'. Allowed values: {sorted(VALID_DISPOSITIONS)}"
        )

    VALID_SORTS = {"newest", "oldest", "recently_updated"}
    if sort and sort not in VALID_SORTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort: '{sort}'. Allowed values: {sorted(VALID_SORTS)}"
        )

    date_from_dt = None
    if date_from:
        try:
            if len(date_from) == 10:
                d = datetime.strptime(date_from, "%Y-%m-%d")
                date_from_dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
            else:
                date_from_dt = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date_from format: '{date_from}'. Expected YYYY-MM-DD or ISO 8601 string."
            )

    date_to_dt = None
    if date_to:
        try:
            if len(date_to) == 10:
                d = datetime.strptime(date_to, "%Y-%m-%d")
                date_to_dt = datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=timezone.utc)
            else:
                date_to_dt = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date_to format: '{date_to}'. Expected YYYY-MM-DD or ISO 8601 string."
            )

    # Enforce RBAC ownership isolation:
    # Inspectors see strictly their own inspections; Admins see all inspections.
    user_scope_id = current_user.user_id if current_user.role != "ADMIN" else None

    return InspectionRepository.list_inspection_summaries(
        db=db,
        user_id=user_scope_id,
        search=search,
        lifecycle_status=lifecycle_status,
        disposition=disposition,
        date_from=date_from_dt,
        date_to=date_to_dt,
        sort=sort,
        page=page,
        page_size=page_size
    )

@router.post("", response_model=InspectionSession)
async def create_inspection(
    reference_date: str = Form(...),
    product_category: str = Form(...),
    capture_plan_id: str = Form(...),
    product_origin: str = Form("UNKNOWN"),
    regulatory_product_class: str = Form("UNKNOWN"),
    date_regulatory_regime: str = Form("UNKNOWN"),
    date_package_exemption: str = Form("UNKNOWN"),
    is_electronic: str = Form("UNKNOWN"),
    package_structure: str = Form("UNKNOWN"),
    alcohol_context: str = Form("UNKNOWN"),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if capture_plan_id not in _capture_plans:
        raise HTTPException(status_code=400, detail="Invalid capture_plan_id")
        
    inspection_id = str(uuid.uuid4())
    owner_id = current_user.user_id
    session = InspectionSession(
        inspection_id=inspection_id,
        reference_date=reference_date,
        product_category=product_category,
        product_origin=product_origin,
        regulatory_product_class=regulatory_product_class,
        date_regulatory_regime=date_regulatory_regime,
        date_package_exemption=date_package_exemption,
        is_electronic=is_electronic,
        package_structure=package_structure,
        alcohol_context=alcohol_context,
        capture_plan_id=capture_plan_id,
        capture_status="INCOMPLETE_INSPECTION",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        created_by_user_id=owner_id,
        captures=[],
        aggregated_candidates=[],
        rule_evaluations=None
    )
    
    # Persist in PostgreSQL
    try:
        InspectionRepository.create_inspection(db, session, created_by_user_id=owner_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="The inspection could not be saved. Check the connection and try again.",
        ) from exc
        
    _inspections[inspection_id] = session
    return session

@router.get("/{inspection_id}", response_model=InspectionSession)
async def get_inspection(
    session: InspectionSession = Depends(get_authorized_inspection)
):
    return session


@router.get("/{inspection_id}/related", response_model=List[RelatedInspectionReference])
async def get_related_inspections(
    limit: int = Query(5, ge=1, le=20),
    session: InspectionSession = Depends(get_authorized_inspection),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return strong, read-only historical matches without affecting this evaluation."""
    owner_scope = current_user.user_id if current_user.role != "ADMIN" else None
    references = []
    for model in InspectionRepository.list_related_reference_candidates(
        db,
        exclude_inspection_id=session.inspection_id,
        user_id=owner_scope,
    ):
        previous = InspectionRepository.inspection_model_to_domain(model)
        match_basis = related_match_basis(session, previous)
        if not match_basis:
            continue
        identity = inspection_identity(previous)
        snapshot = model.report_snapshots[0] if model.report_snapshots else None
        references.append(RelatedInspectionReference(
            inspection_id=model.inspection_id,
            reference_date=model.reference_date,
            created_at=model.created_at.isoformat(),
            lifecycle_status=model.lifecycle_status,
            overall_disposition=snapshot.overall_disposition if snapshot else None,
            product_name=identity["display_product"],
            brand=identity["display_brand"],
            business_names=identity["display_businesses"],
            match_basis=match_basis,
        ))
        if len(references) >= limit:
            break
    return references


@router.get("/{inspection_id}/captures/{capture_id}/image")
async def get_capture_image(
    capture_id: str,
    session: InspectionSession = Depends(get_authorized_inspection),
):
    """Stream one authorized inspection capture without exposing storage access."""
    capture = next(
        (item for item in session.captures if item.capture_id == capture_id),
        None,
    )
    if not capture:
        raise HTTPException(status_code=404, detail="Photograph not found in this inspection.")

    image_bytes = _retrieve_capture_bytes(session.inspection_id, capture)
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photograph is temporarily unavailable. Please retry.",
        )

    if not capture.image_sha256 or hashlib.sha256(image_bytes).hexdigest() != capture.image_sha256:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The stored photograph could not be verified. Officer review is required.",
        )

    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    else:
        media_type = "image/jpeg"
    return Response(
        content=image_bytes,
        media_type=media_type,
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="capture-{capture.capture_id}.{("png" if media_type == "image/png" else "jpg")}"',
        },
    )


@router.post("/{inspection_id}/package-information/review", response_model=InspectionSession)
async def confirm_inspection_package_information(
    session: InspectionSession = Depends(get_authorized_inspection),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    WorkflowService.assert_not_finalized(session)
    if not session.captures:
        raise HTTPException(status_code=409, detail="Take at least one package photograph before confirming the information.")
    previous_review = session.package_information_review
    confirm_package_information_review(
        session,
        user_id=current_user.user_id,
        username=current_user.username,
    )
    try:
        InspectionRepository.update_inspection_state(db, session)
    except Exception as exc:
        session.package_information_review = previous_review
        raise HTTPException(
            status_code=503,
            detail="Your confirmation could not be saved. Please retry.",
        ) from exc
    return session


@router.post("/{inspection_id}/declaration-corrections", response_model=InspectionSession)
async def correct_inspection_declaration(
    request: DeclarationCorrectionRequest,
    session: InspectionSession = Depends(get_authorized_inspection),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    WorkflowService.assert_not_finalized(session)
    try:
        create_officer_declaration_override(
            session,
            candidate_index=request.candidate_index,
            field=request.field,
            confirmed_value=request.confirmed_value,
            reason=request.reason,
            supporting_capture_id=request.supporting_capture_id,
            officer_user_id=current_user.user_id,
            officer_username=current_user.username,
            declaration_role=request.declaration_role,
            date_type=request.date_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    _update_session_compliance(session)
    session.lifecycle_status = WorkflowService.evaluate_auto_transitions(session)
    session.report_snapshot = None
    session.overall_disposition = None
    try:
        InspectionRepository.update_inspection_state(db, session)
    except Exception as exc:
        _inspections.pop(session.inspection_id, None)
        raise HTTPException(
            status_code=503,
            detail="The correction could not be saved. Please retry.",
        ) from exc
    return session

@router.get("/{inspection_id}/workflow", response_model=WorkflowSummary)
async def get_inspection_workflow(
    session: InspectionSession = Depends(get_authorized_inspection)
):
    """
    Retrieves the structured workflow and review summary for the inspection session.
    """
    return WorkflowService.compute_workflow_summary(session)

@router.post("/{inspection_id}/finalize", response_model=InspectionSession)
async def finalize_inspection(
    inspection_id: str,
    session: InspectionSession = Depends(get_authorized_inspection),
    db: Session = Depends(get_db)
):
    """
    Explicitly finalizes the inspection workflow, freezing findings and generating the immutable report snapshot.
    """
    if not package_information_review_is_current(session):
        raise HTTPException(
            status_code=409,
            detail="Please review and confirm the current package information before finalizing the report.",
        )
    plan = _capture_plans.get(session.capture_plan_id, _default_plan)
    finalized_session = WorkflowService.finalize_inspection(session, plan, db=db)
    _inspections[inspection_id] = finalized_session
    return finalized_session

@router.post("/{inspection_id}/captures", response_model=InspectionSession)
async def upload_capture(
    inspection_id: str,
    view_id: str = Form(...),
    image: UploadFile = File(...),
    session: InspectionSession = Depends(get_authorized_inspection),
    db: Session = Depends(get_db)
):
    WorkflowService.assert_not_finalized(session)
    plan = _capture_plans.get(session.capture_plan_id, _default_plan)
    
    valid_view_ids = {v.view_id for v in plan.views}
    if view_id not in valid_view_ids:
        raise HTTPException(status_code=400, detail=f"Invalid view_id. Must be one of {valid_view_ids}")

    # 1. Image Validation & Decode
    decoded_image, sha256_hash = validate_and_decode_image(image)
    
    # Store raw bytes for immutable evidence lookup
    image.file.seek(0)
    raw_image_bytes = image.file.read()
    
    # 2. Image Quality Assessment
    quality_assessment = assess_image_quality(decoded_image)
    
    # 3. OCR Execution
    try:
        ocr_lines = analyze_image(decoded_image)
        pipeline_status = "COMPLETED"
        if not ocr_lines:
            pipeline_status = "OCR_SUCCESS_NO_TEXT"
    except HTTPException as e:
        if e.status_code == 400 and isinstance(e.detail, dict) and e.detail.get("error", {}).get("code") == "NO_USABLE_TEXT_DETECTED":
            ocr_lines = []
            pipeline_status = "OCR_SUCCESS_NO_TEXT"
        else:
            ocr_lines = []
            pipeline_status = "FAILED"
    except Exception as e:
        ocr_lines = []
        pipeline_status = "FAILED"
    
    # 4. Generate Identifiers & Extension-Neutral Deterministic Object Key
    capture_id = str(uuid.uuid4())
    image_id = str(uuid.uuid4()) # For legacy EvidenceItem schema
    media_type = image.content_type or "image/jpeg"
    object_key = f"inspections/{inspection_id}/captures/{capture_id}/source"
    
    # Persist raw bytes in MinIO object storage (single physical object)
    try:
        durable_storage = default_storage_adapter.store(
            key=object_key,
            sha256_hash=sha256_hash,
            data=raw_image_bytes,
            media_type=media_type,
            width=decoded_image.shape[1],
            height=decoded_image.shape[0]
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="The photograph could not be saved. Please keep it on this device and retry.",
        ) from exc
    if durable_storage is False:
        default_storage_adapter.delete(object_key)
        raise HTTPException(
            status_code=503,
            detail="The photograph is waiting to be saved. Please retry when the connection is available.",
        )
    
    # 5. Extraction
    evidence_map = {}
    for i, line in enumerate(ocr_lines):
        evidence_id = str(uuid.uuid4())
        evidence_map[str(i)] = evidence_id
    
    paddle_candidates = extract_candidates(ocr_lines, evidence_map)

    # 5.1 Optional AI_OBSERVED package reading remains in its dedicated audit.
    gemini_audit = await default_contextual_vision_service.analyze_capture(
        inspection_id=inspection_id,
        capture_id=capture_id,
        view_id=view_id,
        image_sha256=sha256_hash,
        image_bytes=raw_image_bytes,
        media_type=media_type,
    )

    # 5.2 Stage 2C is the sole controlled promotion boundary. It preserves both
    # providers' evidence and rejects unsupported contextual inference.
    reconciled_candidates = reconcile_capture_candidates(
        paddle_candidates,
        gemini_audit.analysis,
        capture_id=capture_id,
        view_id=view_id,
    )
    
    # 5.3 Visual Assessment remains anchored only to OCR polygons.
    visual_assessment = assess_capture_visuals(
        capture_id=capture_id,
        view_id=view_id,
        image_width=decoded_image.shape[1],
        image_height=decoded_image.shape[0],
        ocr_lines=ocr_lines,
        field_candidates=paddle_candidates,
        evidence_map=evidence_map,
        quality_assessment=quality_assessment
    )
    
    record = CaptureRecord(
        capture_id=capture_id,
        view_id=view_id,
        evidence_id=image_id,
        image_sha256=sha256_hash,
        object_key=object_key,
        media_type=media_type,
        quality_assessment=quality_assessment,
        visual_assessment=visual_assessment,
        field_candidates=reconciled_candidates,
        deterministic_field_candidates=paddle_candidates,
        processing_provenance=default_capture_processing_provenance(),
        ai_analysis=gemini_audit,
        status=quality_assessment.quality_status,
        pipeline_status=pipeline_status
    )
    
    session.captures.append(record)
    invalidate_package_information_review(session)
    refresh_detected_package_context(session)
    
    # 6. Aggregation
    rebuild_authoritative_candidates(session)
    
    # 7. Completeness Evaluation
    session.capture_status = evaluate_completeness(plan, session.captures)
    
    # 8. Evidence Sufficiency
    session.evidence_sufficiency = evaluate_evidence_sufficiency(plan, session.captures)
    
    # 9. Rule evaluations
    _update_session_compliance(session)
    
    # 9.1 Update lifecycle status
    session.lifecycle_status = WorkflowService.evaluate_auto_transitions(session)
    
    # 10. Persist in PostgreSQL
    try:
        InspectionRepository.add_capture_and_update_inspection_state(
            db,
            session,
            record,
        )
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            default_storage_adapter.delete(object_key)
        except Exception:
            pass
        _inspections.pop(inspection_id, None)
        raise HTTPException(
            status_code=503,
            detail="The photograph could not be confirmed as saved. Keep the device copy and retry.",
        ) from exc
    
    return session

def compute_active_clarification(session: InspectionSession) -> Optional[ClarificationQuestion]:
    if not session.rule_evaluations:
        return None
        
    dismissed = set(session.dismissed_clarifications or [])
    
    # Collect all missing contexts across rules
    missing_by_field = defaultdict(list)
    for eval_res in session.rule_evaluations:
        if eval_res.applicability and getattr(eval_res.applicability, "missing_context", None):
            for mc in eval_res.applicability.missing_context:
                if eval_res.rule_id not in missing_by_field[mc]:
                    missing_by_field[mc].append(eval_res.rule_id)
                    
    # Priority 1: Product Classification (REGULATORY_PRODUCT_CLASS / DATE_REGULATORY_REGIME)
    # Asking broad product type can safely resolve food exception, cosmetics, seeds, or general regime.
    if "PRODUCT_TYPE" not in dismissed and session.regulatory_product_class == "UNKNOWN":
        affects = list(dict.fromkeys(missing_by_field.get("REGULATORY_PRODUCT_CLASS", []) + missing_by_field.get("DATE_REGULATORY_REGIME", [])))
        if affects:
            return ClarificationQuestion(
                question_id="PRODUCT_TYPE",
                title="What type of packaged product is this?",
                description="Selecting the product type applies the appropriate Legal Metrology or regulatory regime.",
                options=[
                    ClarificationOption(
                        id="FOOD",
                        label="Food",
                        context_updates={
                            "regulatory_product_class": "FOOD",
                            "date_regulatory_regime": "FOOD",
                            "date_package_exemption": "NONE"
                        }
                    ),
                    ClarificationOption(
                        id="COSMETIC",
                        label="Cosmetic",
                        context_updates={
                            "regulatory_product_class": "NON_FOOD",
                            "date_regulatory_regime": "COSMETIC",
                            "date_package_exemption": "NONE"
                        }
                    ),
                    ClarificationOption(
                        id="CERTIFIED_SEED",
                        label="Certified Seed",
                        context_updates={
                            "regulatory_product_class": "NON_FOOD",
                            "date_regulatory_regime": "CERTIFIED_SEED",
                            "date_package_exemption": "NONE"
                        }
                    ),
                    ClarificationOption(
                        id="OTHER",
                        label="Other packaged product",
                        context_updates={
                            "regulatory_product_class": "NON_FOOD",
                            "date_regulatory_regime": "GENERAL",
                            "date_package_exemption": "NONE"
                        }
                    ),
                    ClarificationOption(
                        id="NOT_SURE",
                        label="Not sure",
                        context_updates={
                            "dismiss_question_id": "PRODUCT_TYPE"
                        }
                    )
                ],
                affects_rules=affects
            )
            
    # Priority 2: Product Origin (PRODUCT_ORIGIN)
    # Asking origin resolves whether IMPORTER / COUNTRY_OF_ORIGIN rules apply.
    if "PRODUCT_ORIGIN" not in dismissed and session.product_origin == "UNKNOWN":
        affects = missing_by_field.get("PRODUCT_ORIGIN", [])
        if affects:
            return ClarificationQuestion(
                question_id="PRODUCT_ORIGIN",
                title="Is this product imported into India?",
                description="Imported packages require an Importer declaration and Country of Origin under Rule 6.",
                options=[
                    ClarificationOption(
                        id="IMPORTED",
                        label="Yes (Imported)",
                        context_updates={"product_origin": "IMPORTED"}
                    ),
                    ClarificationOption(
                        id="DOMESTIC",
                        label="No (Manufactured in India / Domestic)",
                        context_updates={"product_origin": "DOMESTIC"}
                    ),
                    ClarificationOption(
                        id="NOT_SURE",
                        label="Not sure",
                        context_updates={"dismiss_question_id": "PRODUCT_ORIGIN"}
                    )
                ],
                affects_rules=affects
            )

    # Priority 3: Date Package Exemption (if general date regime is set but exemption is unknown)
    if "DATE_EXEMPTION" not in dismissed and session.date_package_exemption == "UNKNOWN":
        affects = missing_by_field.get("DATE_PACKAGE_EXEMPTION", [])
        if affects:
            return ClarificationQuestion(
                question_id="DATE_EXEMPTION",
                title="Does this product have a specific date exemption?",
                description="Certain commodities like bidi, incense, or domestic LPG are exempted from month/year rules.",
                options=[
                    ClarificationOption(
                        id="NONE",
                        label="No exemption (Standard product)",
                        context_updates={"date_package_exemption": "NONE"}
                    ),
                    ClarificationOption(
                        id="BIDI_OR_INCENSE",
                        label="Bidi or Incense (Exempt)",
                        context_updates={"date_package_exemption": "BIDI_OR_INCENSE"}
                    ),
                    ClarificationOption(
                        id="PSU_LPG",
                        label="PSU Domestic LPG (Exempt)",
                        context_updates={"date_package_exemption": "PSU_DOMESTIC_LPG_14_2_OR_5KG"}
                    ),
                    ClarificationOption(
                        id="NOT_SURE",
                        label="Not sure",
                        context_updates={"dismiss_question_id": "DATE_EXEMPTION"}
                    )
                ],
                affects_rules=affects
            )

    # Priority 4: Unit Sale Price (PACKAGE_STRUCTURE / ALCOHOL_CONTEXT)
    # Suppress questions when USP is independently blocked by missing/unresolved MRP or Net Quantity
    mrp_detected = any(c.field == "MRP" and c.status == "DETECTED" for c in session.aggregated_candidates)
    net_qty_detected = any(c.field == "NET_QUANTITY" and c.status == "DETECTED" for c in session.aggregated_candidates)
    
    if mrp_detected and net_qty_detected:
        if "PACKAGE_STRUCTURE" not in dismissed and session.package_structure == "UNKNOWN":
            affects = missing_by_field.get("PACKAGE_STRUCTURE", [])
            if affects:
                return ClarificationQuestion(
                    question_id="PACKAGE_STRUCTURE",
                    title="What type of package is this?",
                    description="Combination, group, and multi-piece packages are exempted from Unit Sale Price declarations under Rule 26.",
                    options=[
                        ClarificationOption(
                            id="SINGLE",
                            label="Single retail package",
                            context_updates={"package_structure": "SINGLE"}
                        ),
                        ClarificationOption(
                            id="COMBINATION",
                            label="Combination package (Exempt)",
                            context_updates={"package_structure": "COMBINATION"}
                        ),
                        ClarificationOption(
                            id="GROUP",
                            label="Group package (Exempt)",
                            context_updates={"package_structure": "GROUP"}
                        ),
                        ClarificationOption(
                            id="MULTI_PIECE",
                            label="Multi-piece package (Exempt)",
                            context_updates={"package_structure": "MULTI_PIECE"}
                        ),
                        ClarificationOption(
                            id="NOT_SURE",
                            label="Not sure",
                            context_updates={"dismiss_question_id": "PACKAGE_STRUCTURE"}
                        )
                    ],
                    affects_rules=affects
                )
                
        if "ALCOHOL_CONTEXT" not in dismissed and session.alcohol_context == "UNKNOWN":
            affects = missing_by_field.get("ALCOHOL_CONTEXT", [])
            if affects:
                return ClarificationQuestion(
                    question_id="ALCOHOL_CONTEXT",
                    title="Is this an alcoholic beverage?",
                    description="Packages containing alcoholic beverages are governed by State Excise laws and exempted from LMPC Unit Sale Price.",
                    options=[
                        ClarificationOption(
                            id="ALCOHOLIC",
                            label="Yes (Alcoholic)",
                            context_updates={"alcohol_context": "ALCOHOLIC"}
                        ),
                        ClarificationOption(
                            id="NON_ALCOHOLIC",
                            label="No (Non-Alcoholic)",
                            context_updates={"alcohol_context": "NON_ALCOHOLIC"}
                        ),
                        ClarificationOption(
                            id="NOT_SURE",
                            label="Not sure",
                            context_updates={"dismiss_question_id": "ALCOHOL_CONTEXT"}
                        )
                    ],
                    affects_rules=affects
                )

    # Priority 5: Electronic Product (IS_ELECTRONIC)
    # Suppress question when evidence sufficiency is incomplete
    printed_name_detected = any(c.field == "COMMON_GENERIC_NAME" and c.status == "DETECTED" for c in session.aggregated_candidates)
    if not printed_name_detected and session.evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION":
        if "IS_ELECTRONIC" not in dismissed and session.is_electronic == "UNKNOWN":
            affects = missing_by_field.get("IS_ELECTRONIC", [])
            if affects:
                return ClarificationQuestion(
                    question_id="IS_ELECTRONIC",
                    title="Is this an electronic product?",
                    description="Electronic products may qualify for common commodity name declaration via QR code instruction.",
                    options=[
                        ClarificationOption(
                            id="ELECTRONIC",
                            label="Yes (Electronic)",
                            context_updates={"is_electronic": "ELECTRONIC"}
                        ),
                        ClarificationOption(
                            id="NON_ELECTRONIC",
                            label="No (Non-Electronic)",
                            context_updates={"is_electronic": "NON_ELECTRONIC"}
                        ),
                        ClarificationOption(
                            id="NOT_SURE",
                            label="Not sure",
                            context_updates={"dismiss_question_id": "IS_ELECTRONIC"}
                        )
                    ],
                    affects_rules=affects
                )

    return None

def _update_session_compliance(session: InspectionSession):
    if reference_date_obj := datetime.strptime(session.reference_date, "%Y-%m-%d").date():
        legal_candidates = session.deterministic_aggregated_candidates
        if legal_candidates is None:
            legal_candidates = session.aggregated_candidates
        from app.services.officer_review_service import apply_officer_overrides
        from app.services.reproducibility_service import deterministic_candidates_for_capture
        validation_candidates = []
        for capture in session.captures:
            for candidate in deterministic_candidates_for_capture(capture):
                validation_candidates.append(candidate.model_copy(update={
                    "capture_ids": sorted({*candidate.capture_ids, capture.capture_id}),
                }))
        validation_candidates = apply_officer_overrides(
            validation_candidates,
            session.officer_declaration_overrides,
        )
        session.rule_evaluations = orchestrate_compliance(
            candidates=legal_candidates,
            validity_candidates=validation_candidates,
            reference_date=reference_date_obj,
            product_category=session.product_category,
            product_origin=session.product_origin,
            regulatory_category=session.regulatory_product_class,
            is_electronic=session.is_electronic,
            package_structure=session.package_structure,
            alcohol_context=session.alcohol_context,
            date_regulatory_regime=session.date_regulatory_regime,
            date_package_exemption=session.date_package_exemption,
            evidence_sufficiency=session.evidence_sufficiency,
            inspection_complete=(session.capture_status == "COMPLETE_EVIDENCE_CAPTURE")
        )
        
        if session.regulatory_product_class == "FOOD":
            from app.services.fssai_compliance_service import evaluate_fssai_compliance
            session.food_label_evaluations = evaluate_fssai_compliance(
                candidates=legal_candidates,
                validity_candidates=validation_candidates,
                reference_date=reference_date_obj,
                evidence_sufficiency=session.evidence_sufficiency
            )
        else:
            session.food_label_evaluations = []

        from app.services.cross_surface_consistency_service import evaluate_cross_surface_consistency
        consistency_results, food_consistency_results = evaluate_cross_surface_consistency(
            captures=session.captures,
            officer_overrides=session.officer_declaration_overrides,
            legal_metrology_results=session.rule_evaluations,
            food_results=session.food_label_evaluations,
            reference_date=reference_date_obj,
        )
        session.rule_evaluations.extend(consistency_results)
        session.food_label_evaluations.extend(food_consistency_results)
        
        # Aggregate missing context
        context_map = defaultdict(list)
        if session.rule_evaluations:
            for eval_res in session.rule_evaluations:
                if eval_res.applicability and getattr(eval_res.applicability, "missing_context", None):
                    for mc in eval_res.applicability.missing_context:
                        if eval_res.rule_id not in context_map[mc]:
                            context_map[mc].append(eval_res.rule_id)
                            
        session.required_context = [
            RequiredContext(field=k, affects_rules=v)
            for k, v in context_map.items()
        ]
        
        session.active_clarification = compute_active_clarification(session)
        
        session.visual_rule_evaluations = evaluate_visual_legal_rules(
            captures=session.captures,
            aggregated_candidates=legal_candidates,
            reference_date=reference_date_obj
        )
        session.reproducibility = build_reproducibility_record(session)

@router.post("/{inspection_id}/clarifications/dismiss", response_model=InspectionSession)
async def dismiss_clarification(
    inspection_id: str,
    question_id: str = Form(...),
    session: InspectionSession = Depends(get_authorized_inspection),
    db: Session = Depends(get_db)
):
    WorkflowService.assert_not_finalized(session)
    previous = session.model_copy(deep=True)
        
    if session.dismissed_clarifications is None:
        session.dismissed_clarifications = []
        
    if question_id not in session.dismissed_clarifications:
        session.dismissed_clarifications.append(question_id)
        
    _update_session_compliance(session)
    session.lifecycle_status = WorkflowService.evaluate_auto_transitions(session)
    
    try:
        InspectionRepository.update_inspection_state(db, session)
    except Exception as exc:
        _inspections[inspection_id] = previous
        raise HTTPException(status_code=503, detail="Your response could not be saved. Please retry.") from exc
        
    return session

from pydantic import BaseModel

class UpdateContextRequest(BaseModel):
    product_origin: Optional[str] = None
    regulatory_product_class: Optional[str] = None
    date_regulatory_regime: Optional[str] = None
    date_package_exemption: Optional[str] = None
    is_electronic: Optional[str] = None
    package_structure: Optional[str] = None
    alcohol_context: Optional[str] = None
    dismiss_question_id: Optional[str] = None

@router.put("/{inspection_id}/context", response_model=InspectionSession)
@router.patch("/{inspection_id}/context", response_model=InspectionSession)
async def update_inspection_context(
    inspection_id: str,
    request: UpdateContextRequest,
    session: InspectionSession = Depends(get_authorized_inspection),
    db: Session = Depends(get_db)
):
    WorkflowService.assert_not_finalized(session)
    previous = session.model_copy(deep=True)
    if request.dismiss_question_id:
        if session.dismissed_clarifications is None:
            session.dismissed_clarifications = []
        if request.dismiss_question_id not in session.dismissed_clarifications:
            session.dismissed_clarifications.append(request.dismiss_question_id)
            
    # Update explicitly provided fields
    if request.product_origin is not None:
        session.product_origin = request.product_origin
    if request.regulatory_product_class is not None:
        session.regulatory_product_class = request.regulatory_product_class
    if request.date_regulatory_regime is not None:
        session.date_regulatory_regime = request.date_regulatory_regime
    if request.date_package_exemption is not None:
        session.date_package_exemption = request.date_package_exemption
    if request.is_electronic is not None:
        session.is_electronic = request.is_electronic
    if request.package_structure is not None:
        session.package_structure = request.package_structure
    if request.alcohol_context is not None:
        session.alcohol_context = request.alcohol_context
        
    # Re-evaluate compliance based on new context
    _update_session_compliance(session)
    session.lifecycle_status = WorkflowService.evaluate_auto_transitions(session)
    
    try:
        InspectionRepository.update_inspection_state(db, session)
    except Exception as exc:
        _inspections[inspection_id] = previous
        raise HTTPException(status_code=503, detail="The confirmed details could not be saved. Please retry.") from exc
        
    return session

@router.get("/plans/active", response_model=CapturePlan)
async def get_active_plan():
    """Helper for the frontend to know the active prototype plan"""
    return _default_plan


def _resolve_report_snapshot(
    session: InspectionSession,
    plan: CapturePlan,
    db: Session,
) -> InspectionReportSnapshot:
    """Return the current preview or the frozen finalized report.

    Mutable inspections deliberately ignore older database snapshots. A
    correction clears the in-memory preview, so the next request is generated
    from the corrected deterministic assessment. Finalized inspections only
    resolve their already-frozen snapshot and are never regenerated.
    """
    if session.report_snapshot:
        return session.report_snapshot

    if session.lifecycle_status == "FINALIZED":
        try:
            db_report = InspectionRepository.get_latest_report_snapshot_for_inspection(
                db,
                session.inspection_id,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="The finalized report is temporarily unavailable. Please retry.",
            ) from exc
        if not db_report:
            raise HTTPException(
                status_code=409,
                detail="The finalized immutable report could not be located. Administrator review is required.",
            )
        session.report_snapshot = InspectionReportSnapshot.model_validate(
            db_report.snapshot_payload,
        )
        return session.report_snapshot

    report_snapshot = generate_inspection_report(session, plan)
    session.report_snapshot = report_snapshot
    try:
        InspectionRepository.save_report_snapshot(db, report_snapshot)
    except Exception:
        # A mutable preview remains usable in memory. Finalization performs the
        # separate officer-approved freeze and persistence step.
        pass
    return report_snapshot


@router.post("/{inspection_id}/report", response_model=InspectionReportSnapshot)
async def create_inspection_report(
    inspection_id: str,
    session: InspectionSession = Depends(get_authorized_inspection),
    db: Session = Depends(get_db)
):
    """
    Generates an immutable structured report snapshot for the inspection session.
    """
    plan = _capture_plans.get(session.capture_plan_id, _default_plan)
    
    return _resolve_report_snapshot(session, plan, db)

@router.get("/{inspection_id}/report", response_model=InspectionReportSnapshot)
async def get_inspection_report(
    inspection_id: str,
    session: InspectionSession = Depends(get_authorized_inspection),
    db: Session = Depends(get_db)
):
    """
    Retrieves the inspection report snapshot, generating a fresh snapshot if not yet created.
    """
    plan = _capture_plans.get(session.capture_plan_id, _default_plan)
    return _resolve_report_snapshot(session, plan, db)

@router.get("/{inspection_id}/report.pdf")
async def download_inspection_report_pdf(
    inspection_id: str,
    session: InspectionSession = Depends(get_authorized_inspection),
    db: Session = Depends(get_db)
):
    """
    Generates and returns a professional, inspector-ready PDF report
    exclusively from the immutable inspection report snapshot.
    """
    plan = _capture_plans.get(session.capture_plan_id, _default_plan)
    _resolve_report_snapshot(session, plan, db)
        
    # Transiently hydrate evidence image assets from MinIO with SHA-256 verification
    _hydrate_report_evidence_assets(session.report_snapshot, inspection_id)
        
    pdf_bytes = generate_pdf_report(session.report_snapshot)
    filename = f"DRISHTI_Inspection_Report_{session.report_snapshot.metadata.report_id}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@router.get("/{inspection_id}/report.docx")
async def download_inspection_report_docx(
    inspection_id: str,
    session: InspectionSession = Depends(get_authorized_inspection),
    db: Session = Depends(get_db)
):
    """
    Generates and returns a professional, editable Word (.docx) inspection report
    exclusively from the immutable inspection report snapshot.
    """
    plan = _capture_plans.get(session.capture_plan_id, _default_plan)
    _resolve_report_snapshot(session, plan, db)
        
    # Transiently hydrate evidence image assets from MinIO with SHA-256 verification
    _hydrate_report_evidence_assets(session.report_snapshot, inspection_id)
        
    docx_bytes = generate_docx_report(session.report_snapshot)
    filename = f"DRISHTI_Inspection_Report_{session.report_snapshot.metadata.report_id}.docx"
    
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@router.post("/{inspection_id}/evidence_package")
async def export_evidence_package(
    inspection_id: str,
    req: CaseExportRequest,
    session: InspectionSession = Depends(get_authorized_inspection),
    db: Session = Depends(get_db)
):
    """
    Generates an exportable ZIP evidence package for finalized inspections.
    Contains case summary, complaint draft, PDF report, and original evidence images.
    """
    if session.lifecycle_status != "FINALIZED":
        raise HTTPException(
            status_code=400,
            detail="Evidence package can only be exported for finalized inspections."
        )

    # Resolve the already frozen finalized report snapshot.
    plan = _capture_plans.get(session.capture_plan_id, _default_plan)
    _resolve_report_snapshot(session, plan, db)

    if not has_confirmed_deterministic_fail(session.report_snapshot):
        raise HTTPException(
            status_code=400,
            detail="Regulatory escalation requires at least one confirmed deterministic FAIL finding.",
        )

    # Hydration is export-only. Never mutate the frozen snapshot attached to the
    # finalized inspection while assembling downloadable artifacts.
    export_report = session.report_snapshot.model_copy(deep=True)
    _hydrate_report_evidence_assets(export_report, inspection_id)

    # 1. Generate Case Details Text
    details_lines = [
        "==================================================",
        "DRISHTI CASE RECORD",
        "==================================================",
        f"Inspection ID: {session.inspection_id}",
        f"Reference Date: {session.reference_date}",
        f"Product Category: {session.product_category}",
        f"Product Origin: {session.product_origin}",
        f"Regulatory Context: {session.regulatory_product_class}",
        f"Generated At: {datetime.now(timezone.utc).isoformat()}",
        "",
        "SUMMARY COUNTS:",
        f"  Passed Checks: {export_report.summary_counts.statutory_pass_count}",
        f"  Failed Checks: {export_report.summary_counts.statutory_fail_count}",
        f"  Needs Review: {export_report.summary_counts.statutory_review_required_count}",
        f"  Not Applicable: {export_report.summary_counts.statutory_not_applicable_count}",
        "",
        "OBSERVED ISSUES:",
    ]

    details_lines.append("LEGAL METROLOGY VIOLATIONS:")
    lm_fails = [f for f in export_report.declaration_findings if f.status == "FAIL"]
    if lm_fails:
        for finding in lm_fails:
            details_lines.append(f"  - Domain: LEGAL_METROLOGY | {finding.field}: {finding.reason} (Rule: {finding.rule_id}, Ref: {finding.legal_reference})")
    else:
        details_lines.append("  - None")

    if getattr(export_report, "food_label_findings", None):
        details_lines.append("")
        details_lines.append("FOOD LABEL / FSSAI VIOLATIONS:")
        food_fails = [f for f in export_report.food_label_findings if f.status == "FAIL"]
        if food_fails:
            for finding in food_fails:
                details_lines.append(f"  - Domain: FOOD_LABEL_FSSAI | {finding.field}: {finding.reason} (Rule: {finding.rule_id}, Ref: {finding.legal_reference})")
        else:
            details_lines.append("  - None")

    for v_finding in export_report.visual_compliance_findings:
        if v_finding.status == "FAIL":
            details_lines.append(f"- Visual: {v_finding.rule_id}: {v_finding.reason} (Ref: {v_finding.legal_reference})")

    details_text = "\n".join(details_lines)
    manifest = build_evidence_manifest(
        session,
        session.report_snapshot,
        officer_notes=req.officer_notes,
        complaint_draft=req.complaint_draft,
    )

    # 2. Compile Zip in Memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        # Write case details
        zip_file.writestr("case_details.txt", details_text)
        
        # Write complaint draft
        zip_file.writestr("complaint_draft.txt", req.complaint_draft)
        zip_file.writestr("officer_notes.txt", req.officer_notes)
        zip_file.writestr(
            "manifest.json",
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
            ).encode("utf-8"),
        )

        if session.officer_declaration_overrides:
            zip_file.writestr(
                "officer_declaration_corrections.json",
                json.dumps(
                    [
                        override.model_dump(mode="json")
                        for override in session.officer_declaration_overrides
                    ],
                    indent=2,
                ),
            )

        # Write PDF report
        try:
            pdf_bytes = generate_pdf_report(export_report)
            zip_file.writestr(f"DRISHTI_Inspection_Report_{inspection_id}.pdf", pdf_bytes)
        except Exception as e:
            zip_file.writestr("report_generation_error.txt", f"Failed to include PDF report: {str(e)}")

        # Write DOCX report
        try:
            docx_bytes = generate_docx_report(export_report)
            zip_file.writestr(f"DRISHTI_Inspection_Report_{inspection_id}.docx", docx_bytes)
        except Exception:
            pass

        # Write original captured images
        for asset in export_report.evidence_assets:
            capture = next(
                (
                    item
                    for item in session.captures
                    if item.capture_id == asset.capture_id
                ),
                CaptureRecord(
                    capture_id=asset.capture_id,
                    view_id=asset.view_id,
                    image_sha256=asset.image_sha256,
                    media_type=asset.media_type,
                ),
            )
            img_bytes = _retrieve_capture_bytes(inspection_id, capture)

            if img_bytes and hashlib.sha256(img_bytes).hexdigest() == asset.image_sha256:
                ext = ".png" if asset.media_type == "image/png" else ".jpg"
                zip_file.writestr(f"evidence/{asset.view_id}_{asset.capture_id}{ext}", img_bytes)

    zip_bytes = zip_buffer.getvalue()
    filename = f"DRISHTI_Evidence_Package_{inspection_id}.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
