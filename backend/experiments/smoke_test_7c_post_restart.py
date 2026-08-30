import os
import sys
import requests

BASE_URL = os.environ.get("VITE_API_BASE_URL", "http://localhost:8000/api")

def main():
    print("=== POST-RESTART OWNERSHIP & SESSION RECOVERY TEST ===")
    
    # 1. Login as Inspector Alpha
    resp_a = requests.post(f"{BASE_URL}/auth/login", json={"username": "inspector_alpha", "password": "AlphaSecretPass123!"})
    if resp_a.status_code != 200:
        print(f"FAILED to login Alpha post restart: {resp_a.status_code} {resp_a.text}")
        sys.exit(1)
    token_a = resp_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    print(f"   Alpha logged in successfully after restart: user_id={resp_a.json()['user']['user_id']}")

    # 2. Login as Inspector Beta
    resp_b = requests.post(f"{BASE_URL}/auth/login", json={"username": "inspector_beta", "password": "BetaSecretPass123!"})
    assert resp_b.status_code == 200
    token_b = resp_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. Create fresh inspection as Alpha
    create_resp = requests.post(
        f"{BASE_URL}/inspections",
        data={"reference_date": "2026-08-26", "product_category": "GENERIC_RETAIL_PACKAGE", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    assert create_resp.status_code == 200
    insp_id = create_resp.json()["inspection_id"]
    print(f"   Created new inspection post-restart: {insp_id}")

    # 4. Verify Beta is denied (404)
    denied = requests.get(f"{BASE_URL}/inspections/{insp_id}", headers=headers_b)
    assert denied.status_code == 404
    print("   Beta denied (404) on Alpha's new inspection.")

    # 5. Verify Alpha can access and download report
    allowed = requests.get(f"{BASE_URL}/inspections/{insp_id}", headers=headers_a)
    assert allowed.status_code == 200
    print("   Alpha permitted (200) on Alpha's new inspection.")

    print("\n=== POST-RESTART TEST PASSED CLEANLY ===")

if __name__ == "__main__":
    main()
