from typing import Optional, Dict
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.inspection import InspectionSession, CapturePlan
from app.schemas.workflow import WorkflowSummary, InspectionLifecycleStatus
from app.schemas.report import InspectionReportSnapshot
from app.services.report_service import generate_inspection_report
from app.repositories.inspection_repository import InspectionRepository

LIFECYCLE_DISPLAY_NAMES = {
    InspectionLifecycleStatus.DRAFT.value: "New inspection",
    InspectionLifecycleStatus.IN_PROGRESS.value: "Inspection in progress",
    InspectionLifecycleStatus.READY_FOR_REVIEW.value: "Ready for review",
    InspectionLifecycleStatus.FINALIZED.value: "Inspection finalized",
}

class WorkflowService:
    """
    Dedicated domain service managing inspection lifecycle states, valid transitions,
    immutability guards, and structured workflow reviews.
    """

    @staticmethod
    def evaluate_auto_transitions(session: InspectionSession) -> str:
        """
        Computes conservative automatic lifecycle state transitions based on capture and analysis progress.
        Finalized state is strictly immutable and never automatically modified.
        """
        current_status = getattr(session, "lifecycle_status", InspectionLifecycleStatus.DRAFT.value) or InspectionLifecycleStatus.DRAFT.value
        
        # FINALIZED state is strictly locked
        if current_status == InspectionLifecycleStatus.FINALIZED.value:
            return InspectionLifecycleStatus.FINALIZED.value

        # DRAFT: No captures yet
        if not session.captures:
            return InspectionLifecycleStatus.DRAFT.value

        # Analysis completed and results available for inspector review
        if session.rule_evaluations is not None:
            return InspectionLifecycleStatus.READY_FOR_REVIEW.value

        # Captures uploaded or analysis pending
        return InspectionLifecycleStatus.IN_PROGRESS.value

    @staticmethod
    def assert_not_finalized(session: InspectionSession) -> None:
        """
        Guards against mutations on finalized inspections.
        Throws HTTP 409 Conflict if modification is attempted on a locked case.
        """
        current_status = getattr(session, "lifecycle_status", InspectionLifecycleStatus.DRAFT.value) or InspectionLifecycleStatus.DRAFT.value
        if current_status == InspectionLifecycleStatus.FINALIZED.value:
            raise HTTPException(
                status_code=409,
                detail="Cannot modify a finalized inspection. The inspection is locked."
            )

    @staticmethod
    def compute_workflow_summary(session: InspectionSession) -> WorkflowSummary:
        """
        Builds a structured workflow and review summary.
        Calculates categorical statutory findings counts, visual review requirements,
        and action eligibility without arbitrary compliance scores or percentages.
        """
        lifecycle_status = getattr(session, "lifecycle_status", InspectionLifecycleStatus.DRAFT.value) or InspectionLifecycleStatus.DRAFT.value
        display_name = LIFECYCLE_DISPLAY_NAMES.get(lifecycle_status, "Inspection in progress")

        # Statutory checks summary (PASS, FAIL, REVIEW_REQUIRED, NOT_APPLICABLE)
        statutory_summary: Dict[str, int] = {
            "PASS": 0,
            "FAIL": 0,
            "REVIEW_REQUIRED": 0,
            "NOT_APPLICABLE": 0
        }

        has_failures = False
        has_review_req = False

        if session.rule_evaluations:
            for rule_res in session.rule_evaluations:
                status_val = rule_res.status.value if hasattr(rule_res.status, "value") else str(rule_res.status)
                if status_val in statutory_summary:
                    statutory_summary[status_val] += 1
                else:
                    statutory_summary[status_val] = 1

                if status_val == "FAIL":
                    has_failures = True
                elif status_val == "REVIEW_REQUIRED":
                    has_review_req = True

        # Visual observations review counts
        visual_review_count = 0
        if session.visual_rule_evaluations:
            for vr in session.visual_rule_evaluations:
                vr_status = vr.status.value if hasattr(vr.status, "value") else str(vr.status)
                if vr_status in ("REVIEW_REQUIRED", "NOT_EVALUABLE_FROM_CURRENT_CAPTURE"):
                    visual_review_count += 1
                    if vr_status == "REVIEW_REQUIRED":
                        has_review_req = True

        is_finalized = (lifecycle_status == InspectionLifecycleStatus.FINALIZED.value)
        can_finalize = (
            not is_finalized and
            len(session.captures) > 0 and
            session.rule_evaluations is not None
        )

        # Evidence completeness checks (suppressed once case is explicitly finalized)
        has_incomplete = (
            not is_finalized and (
                session.capture_status == "INCOMPLETE_INSPECTION" or
                session.evidence_sufficiency == "INSUFFICIENT_FOR_ABSENCE_EVALUATION"
            )
        )

        report_available = (session.report_snapshot is not None or is_finalized)

        return WorkflowSummary(
            inspection_id=session.inspection_id,
            lifecycle_status=lifecycle_status,
            lifecycle_display_name=display_name,
            can_upload_capture=not is_finalized,
            can_update_context=not is_finalized,
            can_finalize=can_finalize,
            active_clarification=session.active_clarification,
            capture_status=session.capture_status,
            evidence_sufficiency=session.evidence_sufficiency,
            statutory_summary=statutory_summary,
            visual_review_count=visual_review_count,
            has_failures=has_failures,
            has_review_required=has_review_req,
            has_incomplete_evidence=has_incomplete,
            report_available=report_available
        )

    @staticmethod
    def finalize_inspection(
        session: InspectionSession,
        plan: CapturePlan,
        db: Optional[Session] = None
    ) -> InspectionSession:
        """
        Explicitly finalizes an inspection session.
        Validates preconditions (must have captures and analysis results), freezes context/findings,
        generates the immutable report snapshot if not already present, and persists to PostgreSQL.
        """
        current_status = getattr(session, "lifecycle_status", InspectionLifecycleStatus.DRAFT.value) or InspectionLifecycleStatus.DRAFT.value
        
        # If already finalized, return safely
        if current_status == InspectionLifecycleStatus.FINALIZED.value:
            return session

        # Precondition check: Cannot finalize empty DRAFT
        if not session.captures or session.rule_evaluations is None:
            raise HTTPException(
                status_code=400,
                detail="Cannot finalize inspection without captures and completed analysis"
            )

        # Transition lifecycle status to FINALIZED
        session.lifecycle_status = InspectionLifecycleStatus.FINALIZED.value

        # Generate and freeze report snapshot if not already generated
        if not session.report_snapshot:
            snapshot = generate_inspection_report(session, plan)
            session.report_snapshot = snapshot
            session.overall_disposition = snapshot.overall_disposition
            if db:
                try:
                    InspectionRepository.save_report_snapshot(db, snapshot)
                except Exception:
                    pass
        elif not session.overall_disposition:
            session.overall_disposition = session.report_snapshot.overall_disposition

        # Persist finalized state in PostgreSQL
        if db:
            try:
                InspectionRepository.update_inspection_state(db, session)
            except Exception:
                pass

        return session
