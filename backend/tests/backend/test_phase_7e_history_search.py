import io
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import numpy as np
import cv2

from app.main import app
from app.db.session import SessionLocal
from app.core.security import hash_password
from app.repositories.user_repository import UserRepository
from app.repositories.inspection_repository import InspectionRepository
from app.models.inspection import InspectionModel
from app.services.storage_adapter import default_storage_adapter

client = TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def create_synthetic_image(text="HISTORY SAMPLE PACK") -> bytes:
    img = np.full((400, 600, 3), (240, 240, 240), dtype=np.uint8)
    cv2.putText(img, text, (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    success, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()

@pytest.fixture
def history_users(db: Session):
    for uname in ["hist_inspector_a", "hist_inspector_b", "hist_admin"]:
        u = UserRepository.get_by_username(db, uname)
        if u:
            inspections = db.query(InspectionModel).filter(InspectionModel.created_by_user_id == u.user_id).all()
            for insp in inspections:
                db.delete(insp)
            db.delete(u)
    db.commit()

    user_a = UserRepository.create_user(
        db=db,
        username="hist_inspector_a",
        email="hist_a@drishti.local",
        password_hash=hash_password("PassA123!"),
        full_name="Inspector Alpha",
        role="INSPECTOR"
    )

    user_b = UserRepository.create_user(
        db=db,
        username="hist_inspector_b",
        email="hist_b@drishti.local",
        password_hash=hash_password("PassB123!"),
        full_name="Inspector Beta",
        role="INSPECTOR"
    )

    user_admin = UserRepository.create_user(
        db=db,
        username="hist_admin",
        email="hist_admin@drishti.local",
        password_hash=hash_password("AdminPass123!"),
        full_name="Admin User",
        role="ADMIN"
    )

    return {
        "a": user_a,
        "b": user_b,
        "admin": user_admin
    }

def get_auth_headers(username: str, password: str) -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def create_and_finalize_inspection(headers: dict, category: str = "FIN_SAMPLE_PKG", ref_date: str = "2026-08-26") -> str:
    """Helper to create an inspection, upload a capture, and finalize it."""
    resp = client.post(
        "/api/inspections",
        data={"reference_date": ref_date, "product_category": category, "capture_plan_id": "plan_software_1"},
        headers=headers
    )
    assert resp.status_code == 200
    insp_id = resp.json()["inspection_id"]

    img_bytes = create_synthetic_image("PACK MFD 01/2024 MRP Rs 50")
    upload_res = client.post(
        f"/api/inspections/{insp_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers
    )
    assert upload_res.status_code == 200

    review_res = client.post(
        f"/api/inspections/{insp_id}/package-information/review",
        headers=headers,
    )
    assert review_res.status_code == 200
    fin_res = client.post(f"/api/inspections/{insp_id}/finalize", headers=headers)
    assert fin_res.status_code == 200
    return insp_id

# ==============================================================================
# PHASE 7E: INSPECTION HISTORY, SEARCH & FILTER TESTS
# ==============================================================================

def test_1_inspector_lists_own_inspections(history_users):
    """An inspector must list only inspections they created."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    # Create 2 inspections for Inspector A
    resp1 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "PACKAGED_SNACK_A", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    assert resp1.status_code == 200
    id1 = resp1.json()["inspection_id"]

    resp2 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "PACKAGED_BEVERAGE_A", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    assert resp2.status_code == 200
    id2 = resp2.json()["inspection_id"]

    # List history
    resp_list = client.get("/api/inspections", headers=headers_a)
    assert resp_list.status_code == 200
    data = resp_list.json()

    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total_pages"] == 1

    listed_ids = [item["inspection_id"] for item in data["items"]]
    assert id1 in listed_ids
    assert id2 in listed_ids
    for item in data["items"]:
        assert item["created_by_username"] == "hist_inspector_a"

def test_2_inspector_cannot_list_other_inspector_cases(history_users):
    """Inspector Beta must never discover or see Inspector Alpha's inspections in history."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")
    headers_b = get_auth_headers("hist_inspector_b", "PassB123!")

    # Inspector A creates an inspection
    resp_a = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "ALPHA_CASE", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    assert resp_a.status_code == 200
    alpha_id = resp_a.json()["inspection_id"]

    # Inspector B queries history
    resp_b = client.get("/api/inspections", headers=headers_b)
    assert resp_b.status_code == 200
    data_b = resp_b.json()

    assert data_b["total"] == 0
    assert len(data_b["items"]) == 0
    assert alpha_id not in [item["inspection_id"] for item in data_b["items"]]

def test_3_admin_can_list_all_inspections(history_users):
    """Admin user can list inspections across all inspectors."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")
    headers_b = get_auth_headers("hist_inspector_b", "PassB123!")
    headers_admin = get_auth_headers("hist_admin", "AdminPass123!")

    # A creates 1, B creates 1
    resp_a = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "ALPHA_PROD", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    assert resp_a.status_code == 200
    id_a = resp_a.json()["inspection_id"]

    resp_b = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "BETA_PROD", "capture_plan_id": "plan_software_1"},
        headers=headers_b
    )
    assert resp_b.status_code == 200
    id_b = resp_b.json()["inspection_id"]

    # Admin queries history
    resp_admin = client.get("/api/inspections", headers=headers_admin)
    assert resp_admin.status_code == 200
    admin_data = resp_admin.json()

    listed_ids = [item["inspection_id"] for item in admin_data["items"]]
    assert id_a in listed_ids
    assert id_b in listed_ids

def test_4_unauthenticated_request_rejected_401():
    """Unauthenticated call to GET /api/inspections must return 401."""
    resp = client.get("/api/inspections")
    assert resp.status_code == 401

def test_5_lifecycle_status_filter(history_users):
    """Filtering by lifecycle status returns only cases in that state."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    # 1. Draft case
    resp_draft = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "DRAFT_CASE", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    draft_id = resp_draft.json()["inspection_id"]

    # 2. Finalized case
    fin_id = create_and_finalize_inspection(headers_a, category="FIN_CASE")

    # Query DRAFT
    resp_drafts = client.get("/api/inspections?lifecycle_status=DRAFT", headers=headers_a)
    assert resp_drafts.status_code == 200
    draft_ids = [i["inspection_id"] for i in resp_drafts.json()["items"]]
    assert draft_id in draft_ids
    assert fin_id not in draft_ids

    # Query FINALIZED
    resp_fins = client.get("/api/inspections?lifecycle_status=FINALIZED", headers=headers_a)
    assert resp_fins.status_code == 200
    fin_ids = [i["inspection_id"] for i in resp_fins.json()["items"]]
    assert fin_id in fin_ids
    assert draft_id not in fin_ids

def test_6_disposition_filter(history_users):
    """Filtering by report disposition returns only matching evaluated inspections."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    # Create and finalize inspection with 1 capture (partial views -> INCOMPLETE_INSPECTION or REVIEW_REQUIRED)
    insp_id = create_and_finalize_inspection(headers_a, category="DISP_TEST")

    # Get the actual disposition of the finalized inspection
    rep_res = client.get(f"/api/inspections/{insp_id}/report", headers=headers_a)
    assert rep_res.status_code == 200
    actual_disp = rep_res.json()["overall_disposition"]

    # Filter for the actual disposition
    res_match = client.get(f"/api/inspections?disposition={actual_disp}", headers=headers_a)
    assert res_match.status_code == 200
    matched_ids = [i["inspection_id"] for i in res_match.json()["items"]]
    assert insp_id in matched_ids

    # Filter for another non-matching disposition
    other_disp = "VIOLATIONS_FOUND" if actual_disp != "VIOLATIONS_FOUND" else "NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE"
    res_nomatch = client.get(f"/api/inspections?disposition={other_disp}", headers=headers_a)
    assert res_nomatch.status_code == 200
    nomatch_ids = [i["inspection_id"] for i in res_nomatch.json()["items"]]
    assert insp_id not in nomatch_ids

def test_7_date_from_and_date_to_filter(history_users, db: Session):
    """Date filtering restricts results to the specified range on created_at."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    resp = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "DATE_TEST", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    insp_id = resp.json()["inspection_id"]

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    past_str = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")

    # Range covering today: matches
    resp_match = client.get(f"/api/inspections?date_from={today_str}&date_to={tomorrow_str}", headers=headers_a)
    assert resp_match.status_code == 200
    assert insp_id in [i["inspection_id"] for i in resp_match.json()["items"]]

    # Past range: 0 matches
    resp_past = client.get(f"/api/inspections?date_from={past_str}&date_to={yesterday_str}", headers=headers_a)
    assert resp_past.status_code == 200
    assert insp_id not in [i["inspection_id"] for i in resp_past.json()["items"]]

def test_8_sorting_newest(history_users):
    """Newest sort orders by created_at descending."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    resp1 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "SORT_FIRST", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    id1 = resp1.json()["inspection_id"]

    resp2 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "SORT_SECOND", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    id2 = resp2.json()["inspection_id"]

    resp = client.get("/api/inspections?sort=newest", headers=headers_a)
    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = [i["inspection_id"] for i in items]

    assert ids.index(id2) < ids.index(id1)

def test_9_sorting_oldest(history_users):
    """Oldest sort orders by created_at ascending."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    resp1 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "SORT_FIRST", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    id1 = resp1.json()["inspection_id"]

    resp2 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "SORT_SECOND", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    id2 = resp2.json()["inspection_id"]

    resp = client.get("/api/inspections?sort=oldest", headers=headers_a)
    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = [i["inspection_id"] for i in items]

    assert ids.index(id1) < ids.index(id2)

def test_10_sorting_recently_updated(history_users):
    """recently_updated sort orders by updated_at descending."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    resp1 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "UPDATE_A", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    id1 = resp1.json()["inspection_id"]

    resp2 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "UPDATE_B", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    id2 = resp2.json()["inspection_id"]

    # Now update id1 context
    client.put(f"/api/inspections/{id1}/context", json={"product_origin": "DOMESTIC"}, headers=headers_a)

    resp = client.get("/api/inspections?sort=recently_updated", headers=headers_a)
    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = [i["inspection_id"] for i in items]

    assert ids.index(id1) < ids.index(id2)

def test_11_pagination_metadata_and_boundaries(history_users):
    """Backend pagination returns accurate page, page_size, total, and total_pages."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    for i in range(3):
        client.post(
            "/api/inspections",
            data={"reference_date": "2026-08-26", "product_category": f"PAG_ITEM_{i}", "capture_plan_id": "plan_software_1"},
            headers=headers_a
        )

    # Page 1, size 2
    r1 = client.get("/api/inspections?page=1&page_size=2", headers=headers_a)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["page"] == 1
    assert d1["page_size"] == 2
    assert len(d1["items"]) == 2
    assert d1["total"] >= 3
    assert d1["total_pages"] >= 2

    # Page 2, size 2
    r2 = client.get("/api/inspections?page=2&page_size=2", headers=headers_a)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["page"] == 2
    assert len(d2["items"]) >= 1

    # Over-page boundary
    r_over = client.get("/api/inspections?page=999&page_size=10", headers=headers_a)
    assert r_over.status_code == 200
    assert len(r_over.json()["items"]) == 0

def test_12_search_by_inspection_id_substring(history_users):
    """Search matches inspection ID prefix or substring."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    resp = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "SEARCH_TEST_SNACK", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    insp_id = resp.json()["inspection_id"]
    part_id = insp_id[:8]

    resp_search = client.get(f"/api/inspections?search={part_id}", headers=headers_a)
    assert resp_search.status_code == 200
    matched = [i["inspection_id"] for i in resp_search.json()["items"]]
    assert insp_id in matched

def test_13_combined_filters(history_users):
    """Combined search + lifecycle + disposition filters operate conjunctively."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    insp_id = create_and_finalize_inspection(headers_a, category="COMBINED_SNACK")

    rep_res = client.get(f"/api/inspections/{insp_id}/report", headers=headers_a)
    assert rep_res.status_code == 200
    actual_disp = rep_res.json()["overall_disposition"]

    # All matching
    r_match = client.get(
        f"/api/inspections?search=COMBINED&lifecycle_status=FINALIZED&disposition={actual_disp}",
        headers=headers_a
    )
    assert r_match.status_code == 200
    assert insp_id in [i["inspection_id"] for i in r_match.json()["items"]]

    # Mismatching lifecycle
    r_nomatch = client.get(
        f"/api/inspections?search=COMBINED&lifecycle_status=DRAFT&disposition={actual_disp}",
        headers=headers_a
    )
    assert r_nomatch.status_code == 200
    assert insp_id not in [i["inspection_id"] for i in r_nomatch.json()["items"]]

def test_14_empty_result_safe_handling(history_users):
    """Empty results safely return empty list, total=0, total_pages=0."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    resp = client.get("/api/inspections?search=NON_EXISTENT_UUID_99999", headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["total_pages"] == 0

def test_15_finalized_inspection_metadata_included(history_users):
    """Finalized inspection returns correct lifecycle title, report flag, and disposition."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    insp_id = create_and_finalize_inspection(headers_a, category="FINAL_META_TEST")

    resp_list = client.get(f"/api/inspections?search={insp_id}", headers=headers_a)
    assert resp_list.status_code == 200
    items = resp_list.json()["items"]
    assert len(items) == 1
    item = items[0]

    assert item["inspection_id"] == insp_id
    assert item["lifecycle_status"] == "FINALIZED"
    assert item["lifecycle_display_name"] == "Inspection finalized"
    assert item["has_report"] is True
    assert item["overall_disposition"] is not None
    assert item["disposition_display_name"] is not None

def test_16_report_availability_metadata(history_users):
    """Draft case without report snapshot has has_report=False and overall_disposition=None."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    resp = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "NO_REPORT_TEST", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    insp_id = resp.json()["inspection_id"]

    resp_list = client.get(f"/api/inspections?search={insp_id}", headers=headers_a)
    assert resp_list.status_code == 200
    items = resp_list.json()["items"]
    assert len(items) == 1
    item = items[0]

    assert item["has_report"] is False
    assert item["overall_disposition"] is None
    assert item["disposition_display_name"] is None

def test_17_no_minio_retrieval_during_history_list(history_users):
    """Listing inspections must perform zero MinIO object storage retrievals."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    with patch.object(default_storage_adapter, "retrieve", wraps=default_storage_adapter.retrieve) as mock_retrieve:
        resp = client.get("/api/inspections", headers=headers_a)
        assert resp.status_code == 200
        assert mock_retrieve.call_count == 0

def test_18_no_ocr_rerun_during_history_list(history_users):
    """Listing inspections must perform zero PaddleOCR image analyses."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    with patch("app.api.routes.inspections.analyze_image") as mock_ocr:
        resp = client.get("/api/inspections", headers=headers_a)
        assert resp.status_code == 200
        assert mock_ocr.call_count == 0

def test_19_no_legal_recomputation_during_history_list(history_users):
    """Listing inspections must perform zero legal rule engine evaluations."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    with patch("app.api.routes.inspections.orchestrate_compliance") as mock_compliance:
        resp = client.get("/api/inspections", headers=headers_a)
        assert resp.status_code == 200
        assert mock_compliance.call_count == 0

def test_20_invalid_filters_safely_rejected_400(history_users):
    """Invalid filter parameters must return 400 Bad Request."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    # Invalid lifecycle (e.g. COMPLIANT or APPROVED)
    r1 = client.get("/api/inspections?lifecycle_status=COMPLIANT", headers=headers_a)
    assert r1.status_code == 400

    r2 = client.get("/api/inspections?lifecycle_status=APPROVED", headers=headers_a)
    assert r2.status_code == 400

    # Invalid disposition (e.g. CERTIFIED)
    r3 = client.get("/api/inspections?disposition=CERTIFIED", headers=headers_a)
    assert r3.status_code == 400

    # Invalid date
    r4 = client.get("/api/inspections?date_from=invalid-date-format", headers=headers_a)
    assert r4.status_code == 400

    r5 = client.get("/api/inspections?date_to=not_a_date", headers=headers_a)
    assert r5.status_code == 400

    # Invalid sort
    r6 = client.get("/api/inspections?sort=invalid_sort_direction", headers=headers_a)
    assert r6.status_code == 400

def test_21_finalized_case_remains_read_only_after_loading(history_users):
    """A finalized case discovered in history remains strictly immutable."""
    headers_a = get_auth_headers("hist_inspector_a", "PassA123!")

    insp_id = create_and_finalize_inspection(headers_a, category="FINAL_LOCK_TEST")

    # Reopen from API /history
    get_res = client.get(f"/api/inspections/{insp_id}", headers=headers_a)
    assert get_res.status_code == 200
    assert get_res.json()["lifecycle_status"] == "FINALIZED"

    # Attempt capture upload -> 409 Conflict
    img_bytes = create_synthetic_image("IMMUTABLE ATTEMPT")
    upload_res = client.post(
        f"/api/inspections/{insp_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers_a
    )
    assert upload_res.status_code == 409

    # Attempt context update -> 409 Conflict
    ctx_res = client.put(
        f"/api/inspections/{insp_id}/context",
        json={"product_origin": "IMPORTED"},
        headers=headers_a
    )
    assert ctx_res.status_code == 409
