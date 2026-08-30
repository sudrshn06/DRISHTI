import os
import sys
import uuid
import hashlib
import time
import requests
import numpy as np
import cv2

BASE_URL = os.environ.get("VITE_API_BASE_URL", "http://localhost:8000/api")

def make_test_image(text="SMOKE 7C AUTH") -> bytes:
    img = np.full((400, 600, 3), (240, 240, 240), dtype=np.uint8)
    cv2.putText(img, text, (40, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 20, 20), 2)
    success, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()

def main():
    print("=== PHASE 7C MULTI-USER E2E SMOKE TEST ===")
    
    # 1. Login as Inspector Alpha
    print("1. Logging in as Inspector Alpha...")
    resp_a = requests.post(f"{BASE_URL}/auth/login", json={"username": "inspector_alpha", "password": "AlphaSecretPass123!"})
    if resp_a.status_code != 200:
        print(f"FAILED to login Alpha: {resp_a.status_code} {resp_a.text}")
        sys.exit(1)
    token_a = resp_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    print(f"   Alpha logged in successfully: user_id={resp_a.json()['user']['user_id']}")

    # 2. Login as Inspector Beta
    print("2. Logging in as Inspector Beta...")
    resp_b = requests.post(f"{BASE_URL}/auth/login", json={"username": "inspector_beta", "password": "BetaSecretPass123!"})
    if resp_b.status_code != 200:
        print(f"FAILED to login Beta: {resp_b.status_code} {resp_b.text}")
        sys.exit(1)
    token_b = resp_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    print(f"   Beta logged in successfully: user_id={resp_b.json()['user']['user_id']}")

    # 3. Login as Admin
    print("3. Logging in as Admin...")
    resp_adm = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin_example", "password": "AdminSecretPass123!"})
    if resp_adm.status_code != 200:
        print(f"FAILED to login Admin: {resp_adm.status_code} {resp_adm.text}")
        sys.exit(1)
    token_adm = resp_adm.json()["access_token"]
    headers_adm = {"Authorization": f"Bearer {token_adm}"}
    print(f"   Admin logged in successfully: user_id={resp_adm.json()['user']['user_id']}")

    # 4. Inspector Alpha creates inspection
    print("4. Inspector Alpha creating inspection...")
    create_resp = requests.post(
        f"{BASE_URL}/inspections",
        data={"reference_date": "2026-08-26", "product_category": "GENERIC_RETAIL_PACKAGE", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    assert create_resp.status_code == 200
    insp_id = create_resp.json()["inspection_id"]
    print(f"   Inspection created: {insp_id}, owner={create_resp.json().get('created_by_user_id')}")

    # 5. Inspector Alpha uploads capture
    print("5. Inspector Alpha uploading capture...")
    img_data = make_test_image("E2E AUTH CAPTURE")
    upload_resp = requests.post(
        f"{BASE_URL}/inspections/{insp_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("capture.jpg", img_data, "image/jpeg")},
        headers=headers_a
    )
    assert upload_resp.status_code == 200
    print("   Capture uploaded successfully.")

    # 6. Inspector Alpha generates report
    print("6. Inspector Alpha generating report...")
    rep_resp = requests.post(f"{BASE_URL}/inspections/{insp_id}/report", headers=headers_a)
    assert rep_resp.status_code == 200
    rep_id = rep_resp.json()["metadata"]["report_id"]
    print(f"   Report generated: {rep_id}")

    # 7. Inspector Beta attempts to access Inspector Alpha's inspection (Must be 404)
    print("7. Testing IDOR isolation: Inspector Beta attempting to access Alpha's inspection...")
    denied_insp = requests.get(f"{BASE_URL}/inspections/{insp_id}", headers=headers_b)
    assert denied_insp.status_code == 404
    print(f"   Inspection access denied as expected: HTTP {denied_insp.status_code}")

    denied_rep = requests.get(f"{BASE_URL}/inspections/{insp_id}/report", headers=headers_b)
    assert denied_rep.status_code == 404
    print(f"   Report access denied as expected: HTTP {denied_rep.status_code}")

    denied_pdf = requests.get(f"{BASE_URL}/inspections/{insp_id}/report.pdf", headers=headers_b)
    assert denied_pdf.status_code == 404
    print(f"   PDF access denied as expected: HTTP {denied_pdf.status_code}")

    # 8. Admin accesses Inspector Alpha's inspection and downloads PDF
    print("8. Admin accessing Inspector Alpha's inspection...")
    admin_insp = requests.get(f"{BASE_URL}/inspections/{insp_id}", headers=headers_adm)
    assert admin_insp.status_code == 200
    print(f"   Admin inspection access permitted: HTTP {admin_insp.status_code}")

    admin_pdf = requests.get(f"{BASE_URL}/inspections/{insp_id}/report.pdf", headers=headers_adm)
    assert admin_pdf.status_code == 200
    assert len(admin_pdf.content) > 1000
    print(f"   Admin PDF report download permitted: {len(admin_pdf.content)} bytes")

    print("\n=== ALL E2E MULTI-USER ACCESS CONTROL CHECKS PASSED CLEANLY ===")

if __name__ == "__main__":
    main()
