from datetime import datetime
import math
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, func

from app.models.inspection import InspectionModel, CaptureModel, ReportSnapshotModel
from app.models.user import UserModel
from app.schemas.inspection import InspectionSession, CaptureRecord
from app.schemas.officer_review import OfficerDeclarationOverride, PackageInformationReview
from app.schemas.report import InspectionReportSnapshot
from app.schemas.history import (
    InspectionSummaryItem,
    PaginatedInspectionHistory,
    LIFECYCLE_DISPLAY_NAMES,
    DISPOSITION_DISPLAY_NAMES
)
from app.schemas.dashboard import (
    DashboardSummary,
    WorkflowCounts,
    AttentionCounts,
    ReportCounts,
    AdminMetrics
)

class InspectionRepository:
    """
    Repository layer for PostgreSQL persistence operations on Inspections, Captures, and Report Snapshots.
    Keeps database operations cleanly decoupled from domain business logic and legal rules.
    """

    @staticmethod
    def _apply_inspection_state(
        model: InspectionModel,
        session: InspectionSession,
    ) -> None:
        """Apply mutable domain state without committing the active transaction."""
        model.product_origin = session.product_origin
        model.regulatory_product_class = session.regulatory_product_class
        model.date_regulatory_regime = session.date_regulatory_regime
        model.date_package_exemption = session.date_package_exemption
        model.is_electronic = session.is_electronic
        model.package_structure = session.package_structure
        model.alcohol_context = session.alcohol_context
        model.capture_status = session.capture_status
        model.evidence_sufficiency = session.evidence_sufficiency
        model.lifecycle_status = getattr(session, "lifecycle_status", model.lifecycle_status)
        model.dismissed_clarifications = list(session.dismissed_clarifications or [])
        review = session.package_information_review
        model.package_information_review = (
            {
                "reviewed_by_user_id": review.reviewed_by_user_id,
                "reviewed_by_username": review.reviewed_by_username,
                "reviewed_at": review.reviewed_at.isoformat(),
                "basis_fingerprint": review.basis_fingerprint,
            }
            if review
            else None
        )
        model.officer_declaration_overrides = [
            override.model_dump(mode="json")
            for override in (session.officer_declaration_overrides or [])
        ]

    @staticmethod
    def _capture_record_to_model(
        inspection_id: str,
        capture: CaptureRecord,
    ) -> CaptureModel:
        """Build a capture ORM row without flushing or committing it."""
        qa_dict = capture.quality_assessment.model_dump() if hasattr(capture.quality_assessment, "model_dump") else capture.quality_assessment
        va_dict = capture.visual_assessment.model_dump() if hasattr(capture.visual_assessment, "model_dump") else capture.visual_assessment
        cands_list = [c.model_dump() if hasattr(c, "model_dump") else c for c in capture.field_candidates]
        deterministic_cands = capture.deterministic_field_candidates
        if deterministic_cands is None:
            from app.services.reproducibility_service import deterministic_candidates_for_capture
            deterministic_cands = deterministic_candidates_for_capture(capture)
        deterministic_cands_list = [
            c.model_dump() if hasattr(c, "model_dump") else c
            for c in deterministic_cands
        ]
        provenance_dict = (
            capture.processing_provenance.model_dump()
            if hasattr(capture.processing_provenance, "model_dump")
            else capture.processing_provenance
        )
        candidates_payload = {
            "schema_version": "2.0",
            "candidates": cands_list,
            "deterministic_candidates": deterministic_cands_list,
            "processing_provenance": provenance_dict,
        }
        ai_dict = capture.ai_analysis.model_dump(mode="json") if hasattr(capture.ai_analysis, "model_dump") else capture.ai_analysis

        return CaptureModel(
            capture_id=capture.capture_id,
            inspection_id=inspection_id,
            view_id=capture.view_id,
            evidence_id=capture.evidence_id,
            image_sha256=capture.image_sha256 or "",
            object_key=capture.object_key,
            media_type=capture.media_type,
            image_width=capture.visual_assessment.image_width if capture.visual_assessment else None,
            image_height=capture.visual_assessment.image_height if capture.visual_assessment else None,
            status=capture.status,
            pipeline_status=capture.pipeline_status,
            quality_assessment=qa_dict,
            visual_assessment=va_dict,
            field_candidates=candidates_payload,
            ai_analysis=ai_dict,
        )

    @staticmethod
    def create_inspection(db: Session, session: InspectionSession, created_by_user_id: Optional[str] = None) -> InspectionModel:
        """Persists a new inspection record to PostgreSQL."""
        owner_id = created_by_user_id or getattr(session, "created_by_user_id", None)
        model = InspectionModel(
            inspection_id=session.inspection_id,
            reference_date=session.reference_date,
            product_category=session.product_category,
            product_origin=session.product_origin,
            regulatory_product_class=session.regulatory_product_class,
            date_regulatory_regime=session.date_regulatory_regime,
            date_package_exemption=session.date_package_exemption,
            is_electronic=session.is_electronic,
            package_structure=session.package_structure,
            alcohol_context=session.alcohol_context,
            capture_plan_id=session.capture_plan_id,
            capture_status=session.capture_status,
            evidence_sufficiency=session.evidence_sufficiency,
            lifecycle_status=getattr(session, "lifecycle_status", "DRAFT") or "DRAFT",
            created_by_user_id=owner_id,
            dismissed_clarifications=list(session.dismissed_clarifications or []),
            package_information_review=None,
            officer_declaration_overrides=[]
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return model

    @staticmethod
    def get_inspection(db: Session, inspection_id: str) -> Optional[InspectionModel]:
        """Retrieves an inspection model by ID with eager relationships."""
        stmt = select(InspectionModel).where(InspectionModel.inspection_id == inspection_id)
        return db.scalars(stmt).first()

    @staticmethod
    def list_inspections(db: Session, user_id: Optional[str] = None, skip: int = 0, limit: int = 50) -> List[InspectionModel]:
        """Lists inspection models ordered by creation time descending, optionally filtered by owner user_id."""
        stmt = select(InspectionModel)
        if user_id:
            stmt = stmt.where(InspectionModel.created_by_user_id == user_id)
        stmt = stmt.order_by(desc(InspectionModel.created_at)).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def list_inspection_summaries(
        db: Session,
        user_id: Optional[str] = None,
        search: Optional[str] = None,
        lifecycle_status: Optional[str] = None,
        disposition: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 10
    ) -> PaginatedInspectionHistory:
        """
        Retrieves paginated, lightweight inspection summary records with search, filtering, and deterministic sorting.
        Enforces RBAC scoping when user_id is provided.
        Zero MinIO binary retrieval, zero OCR rerun, zero legal recomputation.
        """
        # Subquery for capture count
        capture_count_sub = (
            select(func.count(CaptureModel.capture_id))
            .where(CaptureModel.inspection_id == InspectionModel.inspection_id)
            .scalar_subquery()
        )

        # Subquery for latest report snapshot overall_disposition
        latest_snapshot_sub = (
            select(ReportSnapshotModel.overall_disposition)
            .where(ReportSnapshotModel.inspection_id == InspectionModel.inspection_id)
            .order_by(desc(ReportSnapshotModel.created_at))
            .limit(1)
            .scalar_subquery()
        )

        # Subquery for report count / existence
        report_count_sub = (
            select(func.count(ReportSnapshotModel.report_id))
            .where(ReportSnapshotModel.inspection_id == InspectionModel.inspection_id)
            .scalar_subquery()
        )

        # Subquery for owner username
        owner_username_sub = (
            select(UserModel.username)
            .where(UserModel.user_id == InspectionModel.created_by_user_id)
            .scalar_subquery()
        )

        # Base filter conditions
        conditions = []

        if user_id:
            conditions.append(InspectionModel.created_by_user_id == user_id)

        if search and search.strip():
            term = f"%{search.strip()}%"
            conditions.append(
                InspectionModel.inspection_id.ilike(term) |
                InspectionModel.product_category.ilike(term)
            )

        if lifecycle_status:
            conditions.append(InspectionModel.lifecycle_status == lifecycle_status)

        if disposition:
            conditions.append(latest_snapshot_sub == disposition)

        if date_from:
            conditions.append(InspectionModel.created_at >= date_from)

        if date_to:
            conditions.append(InspectionModel.created_at <= date_to)

        # Count query
        count_stmt = select(func.count(InspectionModel.inspection_id))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total = db.scalar(count_stmt) or 0

        # Query statement with scalar projections
        query_stmt = select(
            InspectionModel.inspection_id,
            InspectionModel.lifecycle_status,
            InspectionModel.created_at,
            InspectionModel.updated_at,
            InspectionModel.reference_date,
            InspectionModel.product_category,
            InspectionModel.created_by_user_id,
            owner_username_sub.label("created_by_username"),
            capture_count_sub.label("capture_count"),
            latest_snapshot_sub.label("overall_disposition"),
            report_count_sub.label("report_count")
        )
        if conditions:
            query_stmt = query_stmt.where(*conditions)

        # Deterministic sorting
        if sort == "oldest":
            query_stmt = query_stmt.order_by(InspectionModel.created_at.asc(), InspectionModel.inspection_id.asc())
        elif sort == "recently_updated":
            query_stmt = query_stmt.order_by(InspectionModel.updated_at.desc(), InspectionModel.inspection_id.desc())
        else: # newest (default)
            query_stmt = query_stmt.order_by(InspectionModel.created_at.desc(), InspectionModel.inspection_id.desc())

        # Pagination
        offset = (page - 1) * page_size
        query_stmt = query_stmt.offset(offset).limit(page_size)

        rows = db.execute(query_stmt).all()

        items = []
        for row in rows:
            created_at_str = row.created_at.isoformat() if hasattr(row.created_at, "isoformat") else str(row.created_at)
            updated_at_str = row.updated_at.isoformat() if hasattr(row.updated_at, "isoformat") else str(row.updated_at)
            disp = row.overall_disposition
            has_rep = bool(row.report_count and row.report_count > 0)

            items.append(
                InspectionSummaryItem(
                    inspection_id=row.inspection_id,
                    lifecycle_status=row.lifecycle_status,
                    lifecycle_display_name=LIFECYCLE_DISPLAY_NAMES.get(row.lifecycle_status, row.lifecycle_status),
                    created_at=created_at_str,
                    updated_at=updated_at_str,
                    capture_count=int(row.capture_count or 0),
                    overall_disposition=disp,
                    disposition_display_name=DISPOSITION_DISPLAY_NAMES.get(disp) if disp else None,
                    has_report=has_rep,
                    reference_date=row.reference_date,
                    product_category=row.product_category,
                    created_by_user_id=row.created_by_user_id,
                    created_by_username=row.created_by_username
                )
            )

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedInspectionHistory(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages
        )

    @staticmethod
    def update_inspection_state(db: Session, session: InspectionSession) -> Optional[InspectionModel]:
        """Updates mutable context and status fields on an existing inspection model."""
        model = db.get(InspectionModel, session.inspection_id)
        if not model:
            return None

        InspectionRepository._apply_inspection_state(model, session)
        try:
            db.commit()
            db.refresh(model)
        except Exception:
            db.rollback()
            raise
        return model

    @staticmethod
    def add_capture(db: Session, inspection_id: str, capture: CaptureRecord) -> CaptureModel:
        """Persists a new capture record attached to an inspection."""
        model = InspectionRepository._capture_record_to_model(inspection_id, capture)
        db.add(model)
        try:
            db.commit()
            db.refresh(model)
        except Exception:
            db.rollback()
            raise
        return model

    @staticmethod
    def add_capture_and_update_inspection_state(
        db: Session,
        session: InspectionSession,
        capture: CaptureRecord,
    ) -> CaptureModel:
        """Persist the capture row and derived inspection state in one commit."""
        inspection_model = db.get(InspectionModel, session.inspection_id)
        if not inspection_model:
            raise ValueError("Inspection not found while saving capture")

        capture_model = InspectionRepository._capture_record_to_model(
            session.inspection_id,
            capture,
        )
        db.add(capture_model)
        InspectionRepository._apply_inspection_state(inspection_model, session)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        return capture_model

    @staticmethod
    def capture_model_to_domain(cap_model: CaptureModel) -> CaptureRecord:
        """Converts a CaptureModel ORM entity to a CaptureRecord domain schema."""
        from app.schemas.image_quality import ImageQualityAssessment
        from app.schemas.visual_assessment import CaptureVisualAssessmentSummary
        from app.schemas.ocr import FieldCandidate, is_authoritative_field_candidate
        from app.schemas.gemini import (
            GeminiCaptureEvidenceReference,
            GeminiPackageAnalysis,
            GeminiPackageAuditRecord,
        )

        qa = ImageQualityAssessment.model_validate(cap_model.quality_assessment) if cap_model.quality_assessment else None
        va = CaptureVisualAssessmentSummary.model_validate(cap_model.visual_assessment) if cap_model.visual_assessment else None
        stored_candidates = cap_model.field_candidates or []
        if isinstance(stored_candidates, dict):
            candidate_rows = stored_candidates.get("candidates", [])
            deterministic_rows = stored_candidates.get("deterministic_candidates")
            provenance_row = stored_candidates.get("processing_provenance")
        else:
            candidate_rows = stored_candidates
            deterministic_rows = None
            provenance_row = None

        cands = [
            candidate
            for candidate in (
                FieldCandidate.model_validate(c)
                for c in candidate_rows
            )
            if is_authoritative_field_candidate(candidate)
        ]
        deterministic_cands = (
            [FieldCandidate.model_validate(c) for c in deterministic_rows]
            if deterministic_rows is not None
            else None
        )
        from app.schemas.reproducibility import CaptureProcessingProvenance
        provenance = (
            CaptureProcessingProvenance.model_validate(provenance_row)
            if provenance_row
            else None
        )
        ai_analysis = None
        if cap_model.ai_analysis:
            if "analysis" in cap_model.ai_analysis:
                ai_analysis = GeminiPackageAuditRecord.model_validate(cap_model.ai_analysis)
            else:
                # Backward-compatible rehydration for captures written by the
                # earliest uncommitted Stage 1 shape. The server-owned capture
                # identity and hash become the trusted audit provenance.
                legacy_analysis = GeminiPackageAnalysis.model_validate(cap_model.ai_analysis)
                ai_analysis = GeminiPackageAuditRecord(
                    audit_id=f"legacy-{cap_model.capture_id}",
                    inspection_id=cap_model.inspection_id,
                    capture_evidence=[GeminiCaptureEvidenceReference(
                        capture_id=cap_model.capture_id,
                        view_id=cap_model.view_id,
                        image_sha256=cap_model.image_sha256,
                    )],
                    analysis=legacy_analysis,
                    created_at=cap_model.created_at,
                )

        return CaptureRecord(
            capture_id=cap_model.capture_id,
            view_id=cap_model.view_id,
            evidence_id=cap_model.evidence_id,
            image_sha256=cap_model.image_sha256,
            object_key=cap_model.object_key,
            media_type=cap_model.media_type or "image/jpeg",
            quality_assessment=qa,
            visual_assessment=va,
            field_candidates=cands,
            deterministic_field_candidates=deterministic_cands,
            processing_provenance=provenance,
            ai_analysis=ai_analysis,
            status=cap_model.status,
            pipeline_status=cap_model.pipeline_status
        )

    @staticmethod
    def inspection_model_to_domain(model: InspectionModel) -> InspectionSession:
        """Rehydrates an InspectionModel ORM entity into a complete domain InspectionSession schema."""
        captures_domain = [InspectionRepository.capture_model_to_domain(c) for c in model.captures]
        
        overrides = [
            OfficerDeclarationOverride.model_validate(item)
            for item in (model.officer_declaration_overrides or [])
        ]
        review = (
            PackageInformationReview.model_validate(model.package_information_review)
            if model.package_information_review
            else None
        )

        # Rebuild both the officer-facing hybrid view and the separate OCR-only
        # legal input stream through the same stable aggregation and overrides.
        from app.services.officer_review_service import apply_officer_overrides
        from app.services.inspection_service import aggregate_candidates
        from app.services.reproducibility_service import deterministic_candidates_for_capture
        all_cands = apply_officer_overrides(aggregate_candidates(captures_domain), overrides)
        deterministic_captures = [
            capture.model_copy(update={
                "field_candidates": deterministic_candidates_for_capture(capture),
            })
            for capture in captures_domain
        ]
        deterministic_cands = apply_officer_overrides(
            aggregate_candidates(deterministic_captures),
            overrides,
        )

        latest_snapshot = None
        if model.lifecycle_status == "FINALIZED" and model.report_snapshots:
            latest_snapshot = InspectionReportSnapshot.model_validate(model.report_snapshots[0].snapshot_payload)

        return InspectionSession(
            inspection_id=model.inspection_id,
            reference_date=model.reference_date,
            product_category=model.product_category,
            product_origin=model.product_origin,
            regulatory_product_class=model.regulatory_product_class,
            date_regulatory_regime=model.date_regulatory_regime,
            date_package_exemption=model.date_package_exemption,
            is_electronic=model.is_electronic,
            package_structure=model.package_structure,
            alcohol_context=model.alcohol_context,
            capture_plan_id=model.capture_plan_id,
            capture_status=model.capture_status,
            evidence_sufficiency=model.evidence_sufficiency,
            lifecycle_status=getattr(model, "lifecycle_status", "DRAFT") or "DRAFT",
            captures=captures_domain,
            aggregated_candidates=all_cands,
            deterministic_aggregated_candidates=deterministic_cands,
            dismissed_clarifications=list(model.dismissed_clarifications or []),
            package_information_review=review,
            officer_declaration_overrides=overrides,
            created_by_user_id=model.created_by_user_id,
            report_snapshot=latest_snapshot
        )

    @staticmethod
    def serialize_report_snapshot_for_storage(snapshot: InspectionReportSnapshot) -> Dict[str, Any]:
        """
        Serializes an InspectionReportSnapshot for PostgreSQL storage.
        Preserves all semantic, legal, context, and evidence metadata/hashes/geometries,
        while stripping large raw image_b64 binary strings to enforce the storage boundary.
        (Binary object storage is handled separately via MinIO/S3 in Phase 7B).
        """
        payload = snapshot.model_dump() if hasattr(snapshot, "model_dump") else dict(snapshot)
        if "evidence_assets" in payload and payload["evidence_assets"]:
            for asset in payload["evidence_assets"]:
                asset["image_b64"] = None
        return payload

    @staticmethod
    def save_report_snapshot(db: Session, snapshot: InspectionReportSnapshot) -> ReportSnapshotModel:
        """Persists an immutable inspection report snapshot record without raw image blobs."""
        payload = InspectionRepository.serialize_report_snapshot_for_storage(snapshot)
        sum_counts = snapshot.summary_counts.model_dump() if hasattr(snapshot.summary_counts, "model_dump") else snapshot.summary_counts

        disp_val = snapshot.overall_disposition.value if hasattr(snapshot.overall_disposition, "value") else str(snapshot.overall_disposition)

        model = ReportSnapshotModel(
            report_id=snapshot.metadata.report_id,
            inspection_id=snapshot.metadata.inspection_id,
            schema_version=snapshot.metadata.report_schema_version,
            generated_at=snapshot.metadata.generated_at,
            overall_disposition=disp_val,
            disposition_reason=snapshot.disposition_reason,
            summary_counts=sum_counts,
            snapshot_payload=payload
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return model

    @staticmethod
    def get_report_snapshot(db: Session, report_id: str) -> Optional[ReportSnapshotModel]:
        """Retrieves a report snapshot record by report ID."""
        stmt = select(ReportSnapshotModel).where(ReportSnapshotModel.report_id == report_id)
        return db.scalars(stmt).first()

    @staticmethod
    def get_latest_report_snapshot_for_inspection(db: Session, inspection_id: str) -> Optional[ReportSnapshotModel]:
        """Retrieves the latest report snapshot record for a given inspection ID."""
        stmt = (
            select(ReportSnapshotModel)
            .where(ReportSnapshotModel.inspection_id == inspection_id)
            .order_by(desc(ReportSnapshotModel.created_at))
        )
        return db.scalars(stmt).first()

    @staticmethod
    def get_capture_by_hash(db: Session, image_sha256: str) -> Optional[CaptureModel]:
        """Looks up a capture model record by its image SHA-256 cryptographic hash."""
        stmt = select(CaptureModel).where(CaptureModel.image_sha256 == image_sha256)
        return db.scalars(stmt).first()

    @staticmethod
    def delete_inspection(db: Session, inspection_id: str) -> bool:
        """Deletes an inspection and cascades to captures and report snapshots."""
        model = db.get(InspectionModel, inspection_id)
        if model:
            db.delete(model)
            db.commit()
            return True
        return False

    @staticmethod
    def get_dashboard_summary(db: Session, user: UserModel) -> DashboardSummary:
        """
        Computes high-performance operational dashboard metrics for the authenticated user.
        - Inspectors see metrics scoped strictly by created_by_user_id == user.user_id.
        - Admins see organization-wide metrics and inspector counts.
        - Employs lightweight SQL aggregate queries with strictly 0 MinIO or OCR calls.
        """
        is_admin = (user.role == "ADMIN")

        # Base filter condition
        insp_filter = []
        if not is_admin:
            insp_filter.append(InspectionModel.created_by_user_id == user.user_id)

        # 1. Workflow counts by lifecycle status
        wf_stmt = (
            select(
                InspectionModel.lifecycle_status,
                func.count(InspectionModel.inspection_id).label("count")
            )
            .where(*insp_filter)
            .group_by(InspectionModel.lifecycle_status)
        )
        wf_rows = db.execute(wf_stmt).all()
        wf_dict = {row.lifecycle_status: row.count for row in wf_rows}

        draft_count = wf_dict.get("DRAFT", 0)
        in_progress_count = wf_dict.get("IN_PROGRESS", 0)
        ready_for_review_count = wf_dict.get("READY_FOR_REVIEW", 0)
        finalized_count = wf_dict.get("FINALIZED", 0)
        total_workflow = draft_count + in_progress_count + ready_for_review_count + finalized_count

        workflow_counts = WorkflowCounts(
            draft=draft_count,
            in_progress=in_progress_count,
            ready_for_review=ready_for_review_count,
            finalized=finalized_count,
            total=total_workflow
        )

        # 2. Attention counts from latest report snapshots
        latest_snapshot_subq = (
            select(
                ReportSnapshotModel.inspection_id,
                ReportSnapshotModel.overall_disposition
            )
            .distinct(ReportSnapshotModel.inspection_id)
            .order_by(ReportSnapshotModel.inspection_id, desc(ReportSnapshotModel.created_at))
            .subquery("latest_snapshots")
        )

        att_stmt = (
            select(
                latest_snapshot_subq.c.overall_disposition,
                func.count(InspectionModel.inspection_id).label("count")
            )
            .select_from(InspectionModel)
            .join(latest_snapshot_subq, InspectionModel.inspection_id == latest_snapshot_subq.c.inspection_id)
            .where(*insp_filter)
            .group_by(latest_snapshot_subq.c.overall_disposition)
        )
        att_rows = db.execute(att_stmt).all()
        att_dict = {row.overall_disposition: row.count for row in att_rows}

        violations_count = att_dict.get("VIOLATIONS_FOUND", 0)
        review_required_count = att_dict.get("REVIEW_REQUIRED", 0)
        incomplete_count = att_dict.get("INCOMPLETE_INSPECTION", 0)
        total_attention = violations_count + review_required_count + incomplete_count

        attention_counts = AttentionCounts(
            violations_found=violations_count,
            review_required=review_required_count,
            incomplete_inspection=incomplete_count,
            total_needing_attention=total_attention
        )

        # 3. Report counts among finalized inspections
        finalized_with_report_stmt = (
            select(func.count(InspectionModel.inspection_id))
            .select_from(InspectionModel)
            .join(latest_snapshot_subq, InspectionModel.inspection_id == latest_snapshot_subq.c.inspection_id)
            .where(InspectionModel.lifecycle_status == "FINALIZED", *insp_filter)
        )
        finalized_with_report_count = db.scalar(finalized_with_report_stmt) or 0
        finalized_without_report_count = max(0, finalized_count - finalized_with_report_count)

        report_counts = ReportCounts(
            finalized_with_report=finalized_with_report_count,
            finalized_without_report=finalized_without_report_count
        )

        # 4. Recent inspections (limit 5, recently updated first)
        recent_paginated = InspectionRepository.list_inspection_summaries(
            db=db,
            user_id=None if is_admin else user.user_id,
            page=1,
            page_size=5,
            sort="recently_updated"
        )
        recent_inspections = recent_paginated.items

        # 5. Admin Metrics if applicable
        admin_metrics = None
        if is_admin:
            total_inspectors_stmt = select(func.count(UserModel.user_id)).where(UserModel.role == "INSPECTOR")
            total_inspectors = db.scalar(total_inspectors_stmt) or 0

            active_inspectors_stmt = select(func.count(UserModel.user_id)).where(
                UserModel.role == "INSPECTOR",
                UserModel.is_active == True
            )
            active_inspectors = db.scalar(active_inspectors_stmt) or 0

            total_sys_stmt = select(func.count(InspectionModel.inspection_id))
            total_system_inspections = db.scalar(total_sys_stmt) or 0

            admin_metrics = AdminMetrics(
                total_inspectors=total_inspectors,
                total_active_inspectors=active_inspectors,
                total_system_inspections=total_system_inspections
            )

        user_display = user.full_name or user.username

        return DashboardSummary(
            workflow_counts=workflow_counts,
            attention_counts=attention_counts,
            report_counts=report_counts,
            recent_inspections=recent_inspections,
            user_role=user.role,
            user_display_name=user_display,
            admin_metrics=admin_metrics
        )
