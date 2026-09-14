import io
import uuid
import zipfile
import json
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.core.security import hash_password, create_access_token
from app.models.user import UserModel
from app.models.inspection import InspectionModel, ReportSnapshotModel
from app.repositories.user_repository import UserRepository
from app.repositories.inspection_repository import InspectionRepository
from app.services.report_service import generate_inspection_report
from app.schemas.compliance import LegalStatus, RuleEvaluationResult
from app.api.routes.inspections import _default_plan

client = TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def test_users(db: Session):
    # Setup test users
    for uname in ["ins_10b_alpha", "ins_10b_beta", "adm_10b"]:
        u = UserRepository.get_by_username(db, uname)
        if u:
            db.delete(u)
    db.commit()

    user_alpha = UserRepository.create_user(
        db=db,
        username="ins_10b_alpha",
        email="alpha10b@drishti.local",
        password_hash=hash_password("Pass123!"),
        full_name="Inspector Alpha",
        role="INSPECTOR"
    )
    user_beta = UserRepository.create_user(
        db=db,
        username="ins_10b_beta",
        email="beta10b@drishti.local",
        password_hash=hash_password("Pass123!"),
        full_name="Inspector Beta",
        role="INSPECTOR"
    )
    user_admin = UserRepository.create_user(
        db=db,
        username="adm_10b",
        email="admin10b@drishti.local",
        password_hash=hash_password("Pass123!"),
        full_name="Admin Admin",
        role="ADMIN"
    )
    db.commit()
    yield user_alpha, user_beta, user_admin

    # Cleanup
    for u in [user_alpha, user_beta, user_admin]:
        db.delete(db.query(UserModel).get(u.user_id))
    db.commit()

@pytest.fixture
def test_inspections(db: Session, test_users):
    user_alpha, user_beta, _ = test_users

    # 1. Finalized session for Alpha
    ins_alpha_final = InspectionModel(
        inspection_id=str(uuid.uuid4()),
        reference_date="2026-08-27",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        lifecycle_status="FINALIZED",
        created_by_user_id=user_alpha.user_id
    )
    db.add(ins_alpha_final)

    # 2. Draft session for Alpha
    ins_alpha_draft = InspectionModel(
        inspection_id=str(uuid.uuid4()),
        reference_date="2026-08-27",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="INCOMPLETE_INSPECTION",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        lifecycle_status="DRAFT",
        created_by_user_id=user_alpha.user_id
    )
    db.add(ins_alpha_draft)
    db.commit()

    # Stage 1.5 finalized cases must carry the immutable snapshot created at
    # officer-approved finalization; they may never regenerate one later.
    finalized_session = InspectionRepository.inspection_model_to_domain(ins_alpha_final)
    finalized_session.rule_evaluations = [RuleEvaluationResult(
        rule_id="MRP_DECLARATION_PRESENCE",
        rule_version="1.0",
        field="MRP",
        status=LegalStatus.FAIL,
        reason="Deterministic test failure",
        evaluated_value="Observed test evidence",
        reference_date=finalized_session.reference_date,
        source_reference="Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 6",
    )]
    finalized_snapshot = generate_inspection_report(finalized_session, _default_plan)
    InspectionRepository.save_report_snapshot(db, finalized_snapshot)

    yield ins_alpha_final, ins_alpha_draft

    # Cleanup
    for ins in [ins_alpha_final, ins_alpha_draft]:
        db.delete(db.query(InspectionModel).get(ins.inspection_id))
    db.commit()


def test_01_unauthenticated_case_access_blocked(test_inspections):
    ins_alpha_final, _ = test_inspections
    res = client.post(
        f"/api/inspections/{ins_alpha_final.inspection_id}/evidence_package",
        json={"complaint_draft": "Some draft content", "officer_notes": "Some notes"}
    )
    assert res.status_code == 401


def test_02_cross_inspector_case_access_blocked(test_users, test_inspections):
    _, user_beta, _ = test_users
    ins_alpha_final, _ = test_inspections
    token = create_access_token(user_id=user_beta.user_id, role=user_beta.role, username=user_beta.username)
    
    res = client.post(
        f"/api/inspections/{ins_alpha_final.inspection_id}/evidence_package",
        headers={"Authorization": f"Bearer {token}"},
        json={"complaint_draft": "Some draft content", "officer_notes": "Some notes"}
    )
    assert res.status_code == 404


def test_03_admin_case_access_allowed(test_users, test_inspections):
    _, _, user_admin = test_users
    ins_alpha_final, _ = test_inspections
    token = create_access_token(user_id=user_admin.user_id, role=user_admin.role, username=user_admin.username)
    
    res = client.post(
        f"/api/inspections/{ins_alpha_final.inspection_id}/evidence_package",
        headers={"Authorization": f"Bearer {token}"},
        json={"complaint_draft": "Some draft content", "officer_notes": "Some notes"}
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"


def test_04_draft_session_evidence_package_blocked(test_users, test_inspections):
    user_alpha, _, _ = test_users
    _, ins_alpha_draft = test_inspections
    token = create_access_token(user_id=user_alpha.user_id, role=user_alpha.role, username=user_alpha.username)
    
    res = client.post(
        f"/api/inspections/{ins_alpha_draft.inspection_id}/evidence_package",
        headers={"Authorization": f"Bearer {token}"},
        json={"complaint_draft": "Some draft", "officer_notes": "Some notes"}
    )
    assert res.status_code == 400
    assert "finalized" in res.json()["detail"].lower()


def test_05_evidence_package_contents_correct(db, test_users, test_inspections):
    user_alpha, _, _ = test_users
    ins_alpha_final, _ = test_inspections
    token = create_access_token(user_id=user_alpha.user_id, role=user_alpha.role, username=user_alpha.username)
    stored_snapshot = (
        db.query(ReportSnapshotModel)
        .filter(ReportSnapshotModel.inspection_id == ins_alpha_final.inspection_id)
        .one()
    )
    frozen_payload = deepcopy(stored_snapshot.snapshot_payload)
    
    res = client.post(
        f"/api/inspections/{ins_alpha_final.inspection_id}/evidence_package",
        headers={"Authorization": f"Bearer {token}"},
        json={"complaint_draft": "TEST DRAFT CONTENT", "officer_notes": "TEST OFFICER NOTES"}
    )
    assert res.status_code == 200
    zip_bytes = res.content
    
    # Read zip contents in-memory
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        namelist = zf.namelist()
        assert "case_details.txt" in namelist
        assert "complaint_draft.txt" in namelist
        assert "officer_notes.txt" in namelist
        assert "manifest.json" in namelist
        
        # Verify contents
        assert zf.read("complaint_draft.txt").decode("utf-8") == "TEST DRAFT CONTENT"
        assert zf.read("officer_notes.txt").decode("utf-8") == "TEST OFFICER NOTES"
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert len(manifest["findings"]["confirmed_deterministic_fail_findings"]) == 1
        assert manifest["deterministic_escalation_summary"]["confirmed_fail_count"] == 1
        assert manifest["officer_material"]["officer_complaint_draft"] == "TEST DRAFT CONTENT"
        assert manifest["external_submission"]["submitted_by_drishti"] is False

    db.expire_all()
    persisted_snapshot = (
        db.query(ReportSnapshotModel)
        .filter(ReportSnapshotModel.inspection_id == ins_alpha_final.inspection_id)
        .one()
    )
    assert persisted_snapshot.snapshot_payload == frozen_payload


def test_06_existing_report_downloads_still_work(test_users, test_inspections):
    user_alpha, _, _ = test_users
    ins_alpha_final, _ = test_inspections
    token = create_access_token(user_id=user_alpha.user_id, role=user_alpha.role, username=user_alpha.username)
    
    pdf_res = client.get(
        f"/api/inspections/{ins_alpha_final.inspection_id}/report.pdf",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"

    docx_res = client.get(
        f"/api/inspections/{ins_alpha_final.inspection_id}/report.docx",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert docx_res.status_code == 200
    assert docx_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
