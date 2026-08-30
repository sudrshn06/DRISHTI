import os
import sys
import time
import json
import statistics
import concurrent.futures
from datetime import date, datetime
import io
from fastapi import UploadFile
import httpx
import gc
import asyncio

# Add /app to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.db.session import SessionLocal
from app.models.user import UserModel
from app.models.inspection import InspectionModel, ReportSnapshotModel
from app.core.config import settings
from app.core.security import create_access_token
from app.services.image_validator import validate_and_decode_image
from app.services.image_quality import assess_image_quality
from app.services.ocr_engine import get_ocr_model, analyze_image
from app.services.candidate_extractor import extract_candidates
from app.services.compliance_service import orchestrate_compliance
from app.services.storage_adapter import default_storage_adapter
from app.services.report_service import generate_inspection_report
from app.services.pdf_report_service import generate_pdf_report
from app.services.docx_report_service import generate_docx_report

def get_process_memory():
    # Read process memory from /proc/self/status on Linux
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])  # in KB
    except:
        pass
    return 0

def measure_ocr_stages():
    print("\n--- 1. OCR & Image Pipeline Benchmarking ---")
    
    img_path = "/app/tests/fixtures/real_world/coke_can.jpg"
    with open(img_path, "rb") as f:
        file_bytes = f.read()
        
    mock_file = UploadFile(
        filename="coke_can.jpg",
        file=io.BytesIO(file_bytes)
    )
    
    # Image Quality / Decode
    t0 = time.perf_counter()
    decoded_image, sha256_hash = validate_and_decode_image(mock_file)
    t1 = time.perf_counter()
    quality_assessment = assess_image_quality(decoded_image)
    t2 = time.perf_counter()
    
    decode_dur = t1 - t0
    quality_dur = t2 - t1
    
    print(f"Image Decoding: {decode_dur*1000:.2f} ms")
    print(f"Image Quality Assessment: {quality_dur*1000:.2f} ms")
    
    # Cold OCR initialization
    t0 = time.perf_counter()
    ocr_model = get_ocr_model()
    cold_ocr_init = time.perf_counter() - t0
    print(f"Cold OCR Initialization Time: {cold_ocr_init:.4f} s")
    
    # Warm OCR runs
    warm_ocr_times = []
    for i in range(3):
        t0 = time.perf_counter()
        ocr_lines = analyze_image(decoded_image)
        warm_ocr_times.append(time.perf_counter() - t0)
    print(f"Warm OCR Inference Times: {[f'{t:.3f} s' for t in warm_ocr_times]}")
    
    # Candidate extraction & compliance
    evidence_map = {str(i): f"ev_{i}" for i in range(len(ocr_lines))}
    t0 = time.perf_counter()
    candidates = extract_candidates(ocr_lines, evidence_map)
    t1 = time.perf_counter()
    results_rules = orchestrate_compliance(
        candidates=candidates,
        reference_date=date(2026, 8, 26),
        product_category="GENERIC_RETAIL_PACKAGE"
    )
    t2 = time.perf_counter()
    
    extraction_dur = t1 - t0
    compliance_dur = t2 - t1
    
    print(f"Candidate Extraction: {extraction_dur*1000:.2f} ms")
    print(f"Compliance Orchestration: {compliance_dur*1000:.2f} ms")
    
    return {
        "decode_dur_ms": decode_dur * 1000,
        "quality_dur_ms": quality_dur * 1000,
        "cold_ocr_init_sec": cold_ocr_init,
        "warm_ocr_mean_sec": statistics.mean(warm_ocr_times),
        "extraction_dur_ms": extraction_dur * 1000,
        "compliance_dur_ms": compliance_dur * 1000
    }

def measure_database():
    print("\n--- 2. Database Scale & Query Timing ---")
    db = SessionLocal()
    try:
        # Check counts
        count_inspections = db.query(InspectionModel).count()
        print(f"Total Inspection Rows: {count_inspections}")
        
        # History query (warm run)
        t_hist = []
        for _ in range(5):
            t0 = time.perf_counter()
            items = db.query(InspectionModel).order_by(InspectionModel.updated_at.desc()).limit(20).all()
            t_hist.append(time.perf_counter() - t0)
        print(f"History listing query latency (mean): {statistics.mean(t_hist)*1000:.2f} ms")
        
        # Filtered history query
        t_filt = []
        for _ in range(5):
            t0 = time.perf_counter()
            items = db.query(InspectionModel).filter(InspectionModel.lifecycle_status == "COMPLETED").limit(20).all()
            t_filt.append(time.perf_counter() - t0)
        print(f"Filtered history query latency (mean): {statistics.mean(t_filt)*1000:.2f} ms")
        
        # Dashboard aggregates
        t_dash = []
        for _ in range(5):
            t0 = time.perf_counter()
            # Simple simulation of dashboard repo aggregates
            total = db.query(InspectionModel).count()
            completed = db.query(InspectionModel).filter(InspectionModel.lifecycle_status == "COMPLETED").count()
            t_dash.append(time.perf_counter() - t0)
        print(f"Dashboard aggregation query latency (mean): {statistics.mean(t_dash)*1000:.2f} ms")
        
        return {
            "total_inspections": count_inspections,
            "mean_history_ms": statistics.mean(t_hist) * 1000,
            "mean_filtered_ms": statistics.mean(t_filt) * 1000,
            "mean_dashboard_ms": statistics.mean(t_dash) * 1000
        }
    finally:
        db.close()

def measure_minio():
    print("\n--- 3. MinIO Storage Benchmarking ---")
    adapter = default_storage_adapter
    bucket = settings.minio_bucket_name
    
    test_data = b"benchmark_durable_storage_data_sha256_verification_test"
    key = "benchmark/test_object.dat"
    
    import hashlib
    sha = hashlib.sha256(test_data).hexdigest()
    
    # Upload
    t0 = time.perf_counter()
    adapter.store(key, sha, test_data, "application/octet-stream")
    upload_dur = time.perf_counter() - t0
    
    # Retrieval
    t0 = time.perf_counter()
    retrieved_bytes = adapter.retrieve(key)
    retrieve_dur = time.perf_counter() - t0
    
    # Clean up
    try:
        adapter.delete(key)
    except:
        pass
        
    print(f"MinIO Upload Latency: {upload_dur*1000:.2f} ms")
    print(f"MinIO Retrieval Latency: {retrieve_dur*1000:.2f} ms")
    
    return {
        "upload_ms": upload_dur * 1000,
        "retrieve_ms": retrieve_dur * 1000
    }

def measure_reports():
    print("\n--- 4. PDF & DOCX Generation Benchmarking ---")
    
    # Load a snapshot template from existing test suites or mock a complete report snapshot
    from tests.backend.test_phase_6b_pdf_report import TEST_PLAN
    db = SessionLocal()
    try:
        user = db.query(UserModel).first()
        from app.schemas.inspection import InspectionSession
        
        session = InspectionSession(
            inspection_id="sess_perf_01",
            reference_date="2026-08-26",
            created_by_user_id=user.user_id if user else None,
            status="COMPLETED",
            product_category="GENERIC_RETAIL_PACKAGE",
            capture_plan_id="plan_software_1",
            capture_status="COMPLETE_EVIDENCE_CAPTURE",
            evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
            captures=[],
            rule_evaluations=[],
            visual_evaluations=[]
        )
        
        snapshot = generate_inspection_report(session, TEST_PLAN)
        
        # Measure PDF
        t0 = time.perf_counter()
        pdf_bytes = generate_pdf_report(snapshot)
        pdf_dur = time.perf_counter() - t0
        
        # Measure DOCX
        t0 = time.perf_counter()
        docx_bytes = generate_docx_report(snapshot)
        docx_dur = time.perf_counter() - t0
        
        print(f"PDF Report Generation Time: {pdf_dur*1000:.2f} ms (Size: {len(pdf_bytes)/1024:.2f} KB)")
        print(f"DOCX Report Generation Time: {docx_dur*1000:.2f} ms (Size: {len(docx_bytes)/1024:.2f} KB)")
        
        return {
            "pdf_gen_ms": pdf_dur * 1000,
            "pdf_size_kb": len(pdf_bytes) / 1024,
            "docx_gen_ms": docx_dur * 1000,
            "docx_size_kb": len(docx_bytes) / 1024
        }
    finally:
        db.close()

async def run_load_test_async(concurrency_levels=[1, 5, 10]):
    print("\n--- 5. API Concurrent Load Benchmarking ---")
    db = SessionLocal()
    user = db.query(UserModel).first()
    db.close()
    
    if not user:
        print("No users found in database. Seeding/Bootstrap check required.")
        return {}
        
    access_token = create_access_token(
        user_id=str(user.user_id),
        role=user.role,
        username=user.username
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    
    endpoints = [
        "/api/health",
        "/api/dashboard",
        "/api/inspections"
    ]
    
    load_results = {}
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Smoke test first (as requested: "Run a tiny smoke check against ONE safe read-only endpoint.")
        print("Running API Smoke Check...")
        t_smoke_0 = time.perf_counter()
        smoke_res = await client.get("/api/health", headers=headers)
        smoke_dur = time.perf_counter() - t_smoke_0
        print(f"Smoke check: {smoke_res.status_code} in {smoke_dur*1000:.2f} ms")
        if smoke_res.status_code != 200:
            print("Warning: Smoke check failed!")
            
        for concurrent_reqs in concurrency_levels:
            print(f"\nEvaluating with concurrency level: {concurrent_reqs}")
            
            for url in endpoints:
                latencies = []
                errors = 0
                
                async def make_request():
                    t0 = time.perf_counter()
                    try:
                        res = await client.get(url, headers=headers)
                        dur = time.perf_counter() - t0
                        if res.status_code == 200:
                            return dur
                        else:
                            return None
                    except Exception:
                        return None
                
                # Run concurrency_reqs * 5 requests in batches of size concurrent_reqs
                num_rounds = 5
                for _ in range(num_rounds):
                    tasks = [make_request() for _ in range(concurrent_reqs)]
                    batch_results = await asyncio.gather(*tasks)
                    for dur in batch_results:
                        if dur is not None:
                            latencies.append(dur)
                        else:
                            errors += 1
                            
                latencies = sorted(latencies)
                if latencies:
                    median = statistics.median(latencies)
                    p95 = latencies[int(len(latencies) * 0.95)]
                    mean_l = statistics.mean(latencies)
                    throughput = len(latencies) / sum(latencies)
                else:
                    median = p95 = mean_l = throughput = 0
                    
                total_reqs = concurrent_reqs * num_rounds
                error_rate = (errors / total_reqs) * 100
                
                print(f"Endpoint: {url}")
                print(f"  Throughput: {throughput:.2f} req/sec")
                print(f"  Median Latency: {median*1000:.2f} ms")
                print(f"  P95 Latency: {p95*1000:.2f} ms")
                print(f"  Error Rate: {error_rate:.1f}%")
                
                load_results[f"{url}_c{concurrent_reqs}"] = {
                    "median_ms": median * 1000,
                    "p95_ms": p95 * 1000,
                    "error_rate": error_rate
                }
                
    return load_results

def run_load_test():
    return asyncio.run(run_load_test_async())

def main():
    print("Starting DRISHTI Performance & Load Baseline Assessment...")
    mem_before = get_process_memory()
    
    ocr_metrics = measure_ocr_stages()
    db_metrics = measure_database()
    minio_metrics = measure_minio()
    report_metrics = measure_reports()
    load_metrics = run_load_test()
    
    gc.collect()
    mem_after = get_process_memory()
    
    print("\n--- 6. Resource Verification Summary ---")
    print(f"Backend RSS Memory Before: {mem_before} KB")
    print(f"Backend RSS Memory After: {mem_after} KB")
    print(f"Memory Net Growth: {mem_after - mem_before} KB")
    
    report_path = "/app/benchmark/results/performance_baseline.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f_rep:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "ocr_metrics": ocr_metrics,
            "db_metrics": db_metrics,
            "minio_metrics": minio_metrics,
            "report_metrics": report_metrics,
            "load_metrics": load_metrics,
            "memory_usage": {
                "rss_before_kb": mem_before,
                "rss_after_kb": mem_after,
                "net_growth_kb": mem_after - mem_before
            }
        }, f_rep, indent=2)
        
    print(f"\nPerformance baseline saved to {report_path}")

if __name__ == "__main__":
    main()
