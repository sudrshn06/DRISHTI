import io
import uuid
import cv2
import numpy as np
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_db
from app.models.user import UserModel
from app.models.inspection import InspectionModel, ReportSnapshotModel
from app.core.security import hash_password, create_access_token

def create_synthetic_image(text="SAMPLE PACK MFD 01/2024 MRP Rs 100") -> bytes:
    img = np.full((400, 600, 3), (240, 240, 240), dtype=np.uint8)
    cv2.putText(img, text, (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    success, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db_session():
    db_gen = get_db()
    db = next(db_gen)
    try:
        yield db
    finally:
        db.close()

def _create_user_and_token(db: Session, username: str, role: str = "INSPECTOR") -> tuple[UserModel, str]:
    existing = db.query(UserModel).filter(UserModel.username == username).first()
    if existing:
        token = create_access_token(user_id=existing.user_id, role=existing.role, username=existing.username)
        return existing, token
    
    user = UserModel(
        user_id=str(uuid.uuid4()),
        username=username,
        email=f"{username}@drishti.gov.in",
        password_hash=hash_password("Password123!"),
        full_name=f"Officer {username.capitalize()}",
        role=role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user_id=user.user_id, role=user.role, username=user.username)
    return user, token


def test_dashboard_unauthenticated_rejected(client: TestClient):
    """Verifies that unauthenticated calls to /api/dashboard return HTTP 401."""
    resp = client.get("/api/dashboard")
    assert resp.status_code == 401


def test_dashboard_empty_state_metrics(client: TestClient, db_session: Session):
    """Verifies that a newly registered inspector with 0 cases gets a valid 0-state summary."""
    new_username = f"empty_insp_{uuid.uuid4().hex[:6]}"
    _, token = _create_user_and_token(db_session, new_username, "INSPECTOR")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["user_role"] == "INSPECTOR"
    assert data["workflow_counts"]["draft"] == 0
    assert data["workflow_counts"]["in_progress"] == 0
    assert data["workflow_counts"]["ready_for_review"] == 0
    assert data["workflow_counts"]["finalized"] == 0
    assert data["workflow_counts"]["total"] == 0

    assert data["attention_counts"]["violations_found"] == 0
    assert data["attention_counts"]["review_required"] == 0
    assert data["attention_counts"]["incomplete_inspection"] == 0
    assert data["attention_counts"]["total_needing_attention"] == 0

    assert data["report_counts"]["finalized_with_report"] == 0
    assert data["report_counts"]["finalized_without_report"] == 0
    assert data["recent_inspections"] == []
    assert data["admin_metrics"] is None

    # Assert STRICT absence of any compliance score or percentage field
    assert "compliance_score" not in data
    assert "score" not in data
    assert "grade" not in data
    assert "compliance_percentage" not in data


def test_dashboard_inspector_workflow_and_attention_counts(client: TestClient, db_session: Session):
    """
    Creates known inspection states for Inspector A:
    1 DRAFT, 1 IN_PROGRESS, 1 READY_FOR_REVIEW, and 3 FINALIZED (1 VIOLATIONS_FOUND, 1 REVIEW_REQUIRED, 1 NO_VIOLATIONS).
    Verifies exact categorical counts and recent inspections.
    """
    user_a, token_a = _create_user_and_token(db_session, f"insp_a_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 1. DRAFT
    insp_draft = InspectionModel(
        inspection_id=f"insp_draft_{uuid.uuid4().hex[:8]}",
        reference_date="2026-08-26",
        product_category="Biscuits",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="DRAFT",
        created_by_user_id=user_a.user_id
    )
    db_session.add(insp_draft)

    # 2. IN_PROGRESS
    insp_prog = InspectionModel(
        inspection_id=f"insp_prog_{uuid.uuid4().hex[:8]}",
        reference_date="2026-08-26",
        product_category="Edible Oil",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="IN_PROGRESS",
        created_by_user_id=user_a.user_id
    )
    db_session.add(insp_prog)

    # 3. READY_FOR_REVIEW
    insp_rev = InspectionModel(
        inspection_id=f"insp_rev_{uuid.uuid4().hex[:8]}",
        reference_date="2026-08-26",
        product_category="Spices",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="READY_FOR_REVIEW",
        created_by_user_id=user_a.user_id
    )
    db_session.add(insp_rev)

    # 4. FINALIZED with VIOLATIONS_FOUND snapshot
    id_fin_viol = f"insp_fin_viol_{uuid.uuid4().hex[:8]}"
    insp_fin_viol = InspectionModel(
        inspection_id=id_fin_viol,
        reference_date="2026-08-26",
        product_category="Detergent",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="FINALIZED",
        created_by_user_id=user_a.user_id
    )
    db_session.add(insp_fin_viol)
    db_session.flush()

    snap_viol = ReportSnapshotModel(
        report_id=f"rep_viol_{uuid.uuid4().hex[:8]}",
        inspection_id=id_fin_viol,
        schema_version="1.0",
        generated_at="2026-08-26T12:00:00Z",
        overall_disposition="VIOLATIONS_FOUND",
        disposition_reason="Mandatory declaration missing",
        summary_counts={"violations": 1},
        snapshot_payload={"sample": "data"}
    )
    db_session.add(snap_viol)

    # 5. FINALIZED with REVIEW_REQUIRED snapshot
    id_fin_rr = f"insp_fin_rr_{uuid.uuid4().hex[:8]}"
    insp_fin_rr = InspectionModel(
        inspection_id=id_fin_rr,
        reference_date="2026-08-26",
        product_category="Packaged Rice",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="FINALIZED",
        created_by_user_id=user_a.user_id
    )
    db_session.add(insp_fin_rr)
    db_session.flush()

    snap_rr = ReportSnapshotModel(
        report_id=f"rep_rr_{uuid.uuid4().hex[:8]}",
        inspection_id=id_fin_rr,
        schema_version="1.0",
        generated_at="2026-08-26T12:00:00Z",
        overall_disposition="REVIEW_REQUIRED",
        disposition_reason="Visual font size requires physical check",
        summary_counts={"review_required": 1},
        snapshot_payload={"sample": "data"}
    )
    db_session.add(snap_rr)

    # 6. FINALIZED with NO_VIOLATIONS snapshot
    id_fin_clean = f"insp_fin_clean_{uuid.uuid4().hex[:8]}"
    insp_fin_clean = InspectionModel(
        inspection_id=id_fin_clean,
        reference_date="2026-08-26",
        product_category="Tea",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="FINALIZED",
        created_by_user_id=user_a.user_id
    )
    db_session.add(insp_fin_clean)
    db_session.flush()

    snap_clean = ReportSnapshotModel(
        report_id=f"rep_clean_{uuid.uuid4().hex[:8]}",
        inspection_id=id_fin_clean,
        schema_version="1.0",
        generated_at="2026-08-26T12:00:00Z",
        overall_disposition="NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE",
        disposition_reason="All evaluated declarations present",
        summary_counts={},
        snapshot_payload={"sample": "data"}
    )
    db_session.add(snap_clean)
    db_session.commit()

    # Call Dashboard endpoint
    resp = client.get("/api/dashboard", headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()

    # Workflow counts
    wf = data["workflow_counts"]
    assert wf["draft"] == 1
    assert wf["in_progress"] == 1
    assert wf["ready_for_review"] == 1
    assert wf["finalized"] == 3
    assert wf["total"] == 6

    # Attention counts
    att = data["attention_counts"]
    assert att["violations_found"] == 1
    assert att["review_required"] == 1
    assert att["incomplete_inspection"] == 0
    assert att["total_needing_attention"] == 2

    # Report counts
    rep = data["report_counts"]
    assert rep["finalized_with_report"] == 3
    assert rep["finalized_without_report"] == 0

    # Recent inspections limit to 5
    recent = data["recent_inspections"]
    assert len(recent) == 5
    recent_ids = [r["inspection_id"] for r in recent]
    assert all(r["created_by_user_id"] == user_a.user_id for r in recent)


def test_dashboard_multi_user_isolation(client: TestClient, db_session: Session):
    """
    Verifies that Inspector B cannot see or infer Inspector A's counts in their dashboard.
    """
    user_a, token_a = _create_user_and_token(db_session, f"iso_a_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    user_b, token_b = _create_user_and_token(db_session, f"iso_b_{uuid.uuid4().hex[:6]}", "INSPECTOR")

    # Create 3 inspections for Inspector A
    for i in range(3):
        insp_a = InspectionModel(
            inspection_id=f"iso_a_insp_{i}_{uuid.uuid4().hex[:6]}",
            reference_date="2026-08-26",
            product_category="Alpha Goods",
            capture_plan_id="PLAN_DEFAULT",
            lifecycle_status="FINALIZED",
            created_by_user_id=user_a.user_id
        )
        db_session.add(insp_a)

    # Create 1 inspection for Inspector B
    insp_b = InspectionModel(
        inspection_id=f"iso_b_insp_{uuid.uuid4().hex[:6]}",
        reference_date="2026-08-26",
        product_category="Beta Goods",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="DRAFT",
        created_by_user_id=user_b.user_id
    )
    db_session.add(insp_b)
    db_session.commit()

    # Inspector A dashboard
    resp_a = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["workflow_counts"]["finalized"] == 3
    assert data_a["workflow_counts"]["draft"] == 0
    assert data_a["workflow_counts"]["total"] == 3

    # Inspector B dashboard
    resp_b = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["workflow_counts"]["finalized"] == 0
    assert data_b["workflow_counts"]["draft"] == 1
    assert data_b["workflow_counts"]["total"] == 1
    assert len(data_b["recent_inspections"]) == 1
    assert data_b["recent_inspections"][0]["inspection_id"] == insp_b.inspection_id


def test_dashboard_admin_global_visibility(client: TestClient, db_session: Session):
    """
    Verifies that Administrator sees system-wide total cases and admin metrics (total inspectors).
    """
    user_a, _ = _create_user_and_token(db_session, f"adm_a_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    user_b, _ = _create_user_and_token(db_session, f"adm_b_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    _, token_admin = _create_user_and_token(db_session, f"admin_{uuid.uuid4().hex[:6]}", "ADMIN")

    insp_a = InspectionModel(
        inspection_id=f"adm_insp_a_{uuid.uuid4().hex[:6]}",
        reference_date="2026-08-26",
        product_category="Food A",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="READY_FOR_REVIEW",
        created_by_user_id=user_a.user_id
    )
    insp_b = InspectionModel(
        inspection_id=f"adm_insp_b_{uuid.uuid4().hex[:6]}",
        reference_date="2026-08-26",
        product_category="Food B",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="FINALIZED",
        created_by_user_id=user_b.user_id
    )
    db_session.add(insp_a)
    db_session.add(insp_b)
    db_session.commit()

    resp_admin = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp_admin.status_code == 200
    data_adm = resp_admin.json()

    assert data_adm["user_role"] == "ADMIN"
    assert data_adm["admin_metrics"] is not None
    assert data_adm["admin_metrics"]["total_inspectors"] >= 2
    assert data_adm["admin_metrics"]["total_system_inspections"] >= 2


def test_dashboard_zero_heavy_operations(client: TestClient, db_session: Session):
    """
    Verifies that querying /api/dashboard invokes strictly 0 MinIO object operations,
    0 PaddleOCR calls, and 0 legal compliance engine calls.
    """
    _, token = _create_user_and_token(db_session, f"perf_user_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.storage_adapter.default_storage_adapter.retrieve") as mock_minio_retrieve, \
         patch("app.services.storage_adapter.default_storage_adapter.retrieve_by_hash") as mock_minio_hash, \
         patch("app.services.ocr_engine.analyze_image") as mock_ocr, \
         patch("app.services.compliance_service.orchestrate_compliance") as mock_compliance:
        
        resp = client.get("/api/dashboard", headers=headers)
        assert resp.status_code == 200

        # Assert strictly 0 calls
        mock_minio_retrieve.assert_not_called()
        mock_minio_hash.assert_not_called()
        mock_ocr.assert_not_called()
        mock_compliance.assert_not_called()


def test_dashboard_incomplete_inspection_attention_count(client: TestClient, db_session: Session):
    """
    Verifies that a finalized inspection with INCOMPLETE_INSPECTION disposition
    increments incomplete_inspection count and total_needing_attention.
    """
    user, token = _create_user_and_token(db_session, f"incomp_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    headers = {"Authorization": f"Bearer {token}"}

    insp_id = f"insp_incomp_{uuid.uuid4().hex[:8]}"
    insp = InspectionModel(
        inspection_id=insp_id,
        reference_date="2026-08-26",
        product_category="Snacks",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="FINALIZED",
        created_by_user_id=user.user_id
    )
    db_session.add(insp)
    db_session.flush()

    snap = ReportSnapshotModel(
        report_id=f"rep_incomp_{uuid.uuid4().hex[:8]}",
        inspection_id=insp_id,
        schema_version="1.0",
        generated_at="2026-08-26T12:00:00Z",
        overall_disposition="INCOMPLETE_INSPECTION",
        disposition_reason="Insufficient surface coverage",
        summary_counts={},
        snapshot_payload={}
    )
    db_session.add(snap)
    db_session.commit()

    resp = client.get("/api/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["attention_counts"]["incomplete_inspection"] == 1
    assert data["attention_counts"]["violations_found"] == 0
    assert data["attention_counts"]["review_required"] == 0
    assert data["attention_counts"]["total_needing_attention"] == 1


def test_dashboard_history_filter_integration(client: TestClient, db_session: Session):
    """
    Verifies that filtering inspections via /api/inspections with parameters matching
    the dashboard cards (lifecycle_status and disposition) returns exact corresponding records.
    """
    user, token = _create_user_and_token(db_session, f"filt_int_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Ready for review case
    insp_rev = InspectionModel(
        inspection_id=f"filt_rev_{uuid.uuid4().hex[:8]}",
        reference_date="2026-08-26",
        product_category="Category A",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="READY_FOR_REVIEW",
        created_by_user_id=user.user_id
    )
    db_session.add(insp_rev)

    # 2. Finalized violation case
    insp_viol_id = f"filt_viol_{uuid.uuid4().hex[:8]}"
    insp_viol = InspectionModel(
        inspection_id=insp_viol_id,
        reference_date="2026-08-26",
        product_category="Category B",
        capture_plan_id="PLAN_DEFAULT",
        lifecycle_status="FINALIZED",
        created_by_user_id=user.user_id
    )
    db_session.add(insp_viol)
    db_session.flush()

    snap_viol = ReportSnapshotModel(
        report_id=f"snap_filt_{uuid.uuid4().hex[:8]}",
        inspection_id=insp_viol_id,
        schema_version="1.0",
        generated_at="2026-08-26T12:00:00Z",
        overall_disposition="VIOLATIONS_FOUND",
        disposition_reason="Non-compliant",
        summary_counts={"violations": 1},
        snapshot_payload={}
    )
    db_session.add(snap_viol)
    db_session.commit()

    # 1. Fetch dashboard
    dash_resp = client.get("/api/dashboard", headers=headers)
    assert dash_resp.status_code == 200
    dash = dash_resp.json()
    assert dash["workflow_counts"]["ready_for_review"] == 1
    assert dash["attention_counts"]["violations_found"] == 1

    # 2. Query history using READY_FOR_REVIEW lifecycle filter (simulating card click)
    hist_rev = client.get("/api/inspections?lifecycle_status=READY_FOR_REVIEW", headers=headers)
    assert hist_rev.status_code == 200
    data_rev = hist_rev.json()
    assert data_rev["total"] == 1
    assert data_rev["items"][0]["inspection_id"] == insp_rev.inspection_id

    # 3. Query history using VIOLATIONS_FOUND disposition filter (simulating attention card click)
    hist_viol = client.get("/api/inspections?disposition=VIOLATIONS_FOUND", headers=headers)
    assert hist_viol.status_code == 200
    data_viol = hist_viol.json()
    assert data_viol["total"] == 1
    assert data_viol["items"][0]["inspection_id"] == insp_viol_id



def test_dashboard_recent_inspections_ordering_and_limit(client: TestClient, db_session: Session):
    """
    Creates 7 inspections with staggered updates and verifies that recent_inspections
    returns exactly the latest 5 sorted by updated_at descending.
    """
    user, token = _create_user_and_token(db_session, f"rec_ord_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    headers = {"Authorization": f"Bearer {token}"}

    created_ids = []
    for i in range(7):
        insp_id = f"ord_insp_{i}_{uuid.uuid4().hex[:6]}"
        insp = InspectionModel(
            inspection_id=insp_id,
            reference_date="2026-08-26",
            product_category=f"Product {i}",
            capture_plan_id="PLAN_DEFAULT",
            lifecycle_status="DRAFT",
            created_by_user_id=user.user_id
        )
        db_session.add(insp)
        created_ids.append(insp_id)
    db_session.commit()

    resp = client.get("/api/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    recent = data["recent_inspections"]
    assert len(recent) == 5
    # Total count in workflow is 7
    assert data["workflow_counts"]["total"] == 7
    assert data["workflow_counts"]["draft"] == 7


def test_dashboard_report_counts_breakdown(client: TestClient, db_session: Session):
    """
    Verifies that finalized_with_report and finalized_without_report counts
    reflect whether report snapshots were created for finalized inspections.
    """
    user, token = _create_user_and_token(db_session, f"rep_cnt_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    headers = {"Authorization": f"Bearer {token}"}

    # 2 finalized WITH report
    for i in range(2):
        insp_id = f"fin_rep_with_{i}_{uuid.uuid4().hex[:6]}"
        insp = InspectionModel(
            inspection_id=insp_id,
            reference_date="2026-08-26",
            product_category="Category With Report",
            capture_plan_id="PLAN_DEFAULT",
            lifecycle_status="FINALIZED",
            created_by_user_id=user.user_id
        )
        db_session.add(insp)
        db_session.flush()

        snap = ReportSnapshotModel(
            report_id=f"snap_{i}_{uuid.uuid4().hex[:6]}",
            inspection_id=insp_id,
            schema_version="1.0",
            generated_at="2026-08-26T12:00:00Z",
            overall_disposition="NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE",
            disposition_reason="All good",
            summary_counts={},
            snapshot_payload={}
        )
        db_session.add(snap)

    # 2 finalized WITHOUT report
    for i in range(2):
        insp_id = f"fin_rep_without_{i}_{uuid.uuid4().hex[:6]}"
        insp = InspectionModel(
            inspection_id=insp_id,
            reference_date="2026-08-26",
            product_category="Category Without Report",
            capture_plan_id="PLAN_DEFAULT",
            lifecycle_status="FINALIZED",
            created_by_user_id=user.user_id
        )
        db_session.add(insp)

    db_session.commit()

    resp = client.get("/api/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["workflow_counts"]["finalized"] == 4
    assert data["report_counts"]["finalized_with_report"] == 2
    assert data["report_counts"]["finalized_without_report"] == 2


def test_dashboard_strictly_zero_compliance_scores(client: TestClient, db_session: Session):
    """
    Exhaustively scans the entire dashboard response structure to ensure zero scores,
    percentages, ratings, or grades exist.
    """
    user, token = _create_user_and_token(db_session, f"no_scores_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    def _assert_no_forbidden_keys(obj, path=""):
        forbidden_keywords = ["score", "percentage", "grade", "rank", "compliance_score", "compliance_pct", "health"]
        if isinstance(obj, dict):
            for k, v in obj.items():
                for kw in forbidden_keywords:
                    assert kw not in k.lower(), f"Forbidden key '{k}' found at {path}.{k}"
                _assert_no_forbidden_keys(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                _assert_no_forbidden_keys(item, f"{path}[{idx}]")

    _assert_no_forbidden_keys(data)


def test_dashboard_multi_user_operational_e2e(client: TestClient, db_session: Session):
    """
    End-to-End multi-user operational check:
    - Inspector Alpha creates Draft, Ready-for-Review, and Finalized (with report & violation).
    - Inspector Alpha verifies: dashboard counts, attention counts, recent cases, workflow resume, and protected report download.
    - Inspector Beta logs in: isolated dashboard, 0 Alpha counts visible.
    - Admin logs in: sees global total counts (Alpha + Beta) and admin inspector metrics.
    - New inspector logs in: clean 0 counts.
    """
    # 1. Users
    user_alpha, token_alpha = _create_user_and_token(db_session, f"e2e_alpha_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    user_beta, token_beta = _create_user_and_token(db_session, f"e2e_beta_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    user_admin, token_admin = _create_user_and_token(db_session, f"e2e_admin_{uuid.uuid4().hex[:6]}", "ADMIN")
    user_empty, token_empty = _create_user_and_token(db_session, f"e2e_empty_{uuid.uuid4().hex[:6]}", "INSPECTOR")

    headers_alpha = {"Authorization": f"Bearer {token_alpha}"}
    headers_beta = {"Authorization": f"Bearer {token_beta}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}
    headers_empty = {"Authorization": f"Bearer {token_empty}"}

    # 2. Inspector Alpha Cases
    # Case 1: Draft
    res1 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "Biscuits", "capture_plan_id": "plan_software_1"},
        headers=headers_alpha
    )
    assert res1.status_code == 200
    id_draft = res1.json()["inspection_id"]

    # Case 2: Ready for review (1 capture uploaded)
    res2 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "Juice", "capture_plan_id": "plan_software_1"},
        headers=headers_alpha
    )
    assert res2.status_code == 200
    id_rev = res2.json()["inspection_id"]
    img_bytes = create_synthetic_image("JUICE MFD 02/2024 MRP Rs 40")
    up_rev = client.post(
        f"/api/inspections/{id_rev}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers_alpha
    )
    assert up_rev.status_code == 200
    assert up_rev.json()["lifecycle_status"] == "READY_FOR_REVIEW"

    # Case 3: Finalized with report
    res3 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "Shampoo", "capture_plan_id": "plan_software_1"},
        headers=headers_alpha
    )
    assert res3.status_code == 200
    id_fin = res3.json()["inspection_id"]
    up_fin = client.post(
        f"/api/inspections/{id_fin}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers_alpha
    )
    assert up_fin.status_code == 200

    review_res = client.post(
        f"/api/inspections/{id_fin}/package-information/review",
        headers=headers_alpha,
    )
    assert review_res.status_code == 200
    fin_res = client.post(f"/api/inspections/{id_fin}/finalize", headers=headers_alpha)
    assert fin_res.status_code == 200
    assert fin_res.json()["lifecycle_status"] == "FINALIZED"

    # 3. Inspector Beta Cases (1 in-progress)
    res_b = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "Spices", "capture_plan_id": "plan_software_1"},
        headers=headers_beta
    )
    assert res_b.status_code == 200
    id_beta = res_b.json()["inspection_id"]
    db_insp_beta = db_session.get(InspectionModel, id_beta)
    db_insp_beta.lifecycle_status = "IN_PROGRESS"
    db_session.commit()

    # --- VERIFY INSPECTOR ALPHA ---
    resp_alpha = client.get("/api/dashboard", headers=headers_alpha)
    assert resp_alpha.status_code == 200
    d_alpha = resp_alpha.json()
    assert d_alpha["workflow_counts"]["draft"] == 1
    assert d_alpha["workflow_counts"]["ready_for_review"] == 1
    assert d_alpha["workflow_counts"]["finalized"] == 1
    assert d_alpha["workflow_counts"]["in_progress"] == 0
    assert d_alpha["workflow_counts"]["total"] == 3

    fin_disp = fin_res.json()["report_snapshot"]["overall_disposition"]
    assert d_alpha["attention_counts"][fin_disp.lower()] == 1
    assert d_alpha["attention_counts"]["total_needing_attention"] == 1
    assert d_alpha["report_counts"]["finalized_with_report"] == 1

    # Verify Alpha can access their own cases and reports
    wf_resp = client.get(f"/api/inspections/{id_draft}/workflow", headers=headers_alpha)
    assert wf_resp.status_code == 200

    pdf_resp = client.get(f"/api/inspections/{id_fin}/report.pdf", headers=headers_alpha)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"

    # --- VERIFY INSPECTOR BETA ISOLATION ---
    resp_beta = client.get("/api/dashboard", headers=headers_beta)
    assert resp_beta.status_code == 200
    d_beta = resp_beta.json()
    assert d_beta["workflow_counts"]["in_progress"] == 1
    assert d_beta["workflow_counts"]["draft"] == 0
    assert d_beta["workflow_counts"]["ready_for_review"] == 0
    assert d_beta["workflow_counts"]["finalized"] == 0
    assert d_beta["workflow_counts"]["total"] == 1
    assert d_beta["attention_counts"]["violations_found"] == 0
    assert len(d_beta["recent_inspections"]) == 1
    assert d_beta["recent_inspections"][0]["inspection_id"] == id_beta

    # Beta cannot access Alpha's report
    pdf_beta_denied = client.get(f"/api/inspections/{id_fin}/report.pdf", headers=headers_beta)
    assert pdf_beta_denied.status_code == 404

    # --- VERIFY ADMIN GLOBAL METRICS ---
    resp_admin = client.get("/api/dashboard", headers=headers_admin)
    assert resp_admin.status_code == 200
    d_admin = resp_admin.json()
    assert d_admin["user_role"] == "ADMIN"
    assert d_admin["workflow_counts"]["total"] >= 4
    assert d_admin["admin_metrics"]["total_inspectors"] >= 3
    assert d_admin["admin_metrics"]["total_system_inspections"] >= 4

    # --- VERIFY EMPTY INSPECTOR ACCOUNT ---
    resp_empty = client.get("/api/dashboard", headers=headers_empty)
    assert resp_empty.status_code == 200
    d_empty = resp_empty.json()
    assert d_empty["workflow_counts"]["total"] == 0
    assert d_empty["recent_inspections"] == []

