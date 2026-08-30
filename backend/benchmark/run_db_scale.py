import os
import sys
import time
import json
import uuid
import statistics
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session

# Add /app to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import SessionLocal
from app.models.user import UserModel
from app.models.inspection import InspectionModel, ReportSnapshotModel, CaptureModel

def get_row_counts(db: Session):
    insp_count = db.execute(text("SELECT count(*) FROM inspections")).scalar()
    cap_count = db.execute(text("SELECT count(*) FROM captures")).scalar()
    rep_count = db.execute(text("SELECT count(*) FROM report_snapshots")).scalar()
    return insp_count, cap_count, rep_count

def get_indexes(db: Session):
    res = db.execute(text("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'")).fetchall()
    return [{"table": r[0], "index": r[1], "definition": r[2]} for r in res]

def measure_queries(db: Session, user_id: str, results_dict: dict, label: str):
    print(f"\nMeasuring queries at scale: {label}...")
    
    # We will run 10 iterations of each query to compute statistics
    queries = {
        "A_recent_history": text(
            "SELECT * FROM inspections WHERE created_by_user_id = :uid ORDER BY created_at DESC LIMIT 10"
        ),
        "B_history_pagination": text(
            "SELECT * FROM inspections WHERE created_by_user_id = :uid ORDER BY created_at DESC LIMIT 10 OFFSET 50"
        ),
        "C_status_filter": text(
            "SELECT * FROM inspections WHERE created_by_user_id = :uid AND lifecycle_status = 'DRAFT' ORDER BY created_at DESC LIMIT 10"
        ),
        "D_date_filter": text(
            "SELECT * FROM inspections WHERE created_by_user_id = :uid AND created_at >= :date_from ORDER BY created_at DESC LIMIT 10"
        ),
        "E_owner_scoped": text(
            "SELECT * FROM inspections WHERE created_by_user_id = :uid"
        ),
        "F_combined_filters": text(
            "SELECT * FROM inspections WHERE created_by_user_id = :uid AND lifecycle_status = 'DRAFT' AND created_at >= :date_from ORDER BY created_at DESC LIMIT 10"
        ),
        "G_single_lookup": text(
            "SELECT * FROM inspections WHERE inspection_id = :insp_id"
        ),
        "H_report_snapshot_lookup": text(
            "SELECT * FROM report_snapshots WHERE inspection_id = :insp_id ORDER BY created_at DESC LIMIT 1"
        ),
        "I_dashboard_counts": text(
            "SELECT lifecycle_status, count(*) FROM inspections WHERE created_by_user_id = :uid GROUP BY lifecycle_status"
        ),
        "J_dashboard_aggregations": text(
            "SELECT count(*), max(created_at) FROM inspections WHERE created_by_user_id = :uid"
        )
    }
    
    # Setup parameters
    date_from = datetime.now(timezone.utc) - timedelta(days=30)
    
    # Find a sample inspection ID for lookup tests
    sample_insp_id = db.execute(text("SELECT inspection_id FROM inspections LIMIT 1")).scalar()
    if not sample_insp_id:
        sample_insp_id = str(uuid.uuid4())
        
    uid = user_id
    
    scale_results = {}
    
    for q_name, q_stmt in queries.items():
        durations = []
        for _ in range(10):
            t0 = time.perf_counter()
            db.execute(q_stmt, {"uid": uid, "date_from": date_from, "insp_id": sample_insp_id}).fetchall()
            durations.append((time.perf_counter() - t0) * 1000.0) # ms
            
        scale_results[q_name] = {
            "min": min(durations),
            "median": statistics.median(durations),
            "mean": statistics.mean(durations),
            "max": max(durations),
            "p95": sorted(durations)[-1]  # 10 samples -> max is the P95/P100
        }
        print(f"  {q_name:<30}: median={scale_results[q_name]['median']:.2f}ms, mean={scale_results[q_name]['mean']:.2f}ms")
        
    results_dict[label] = scale_results

def run_scale_validation():
    db = SessionLocal()
    
    # 1. Baseline
    print("--- 1. Baseline counts and indexes ---")
    insp_count, cap_count, rep_count = get_row_counts(db)
    print(f"Baseline rows: Inspections={insp_count}, Captures={cap_count}, Report Snapshots={rep_count}")
    
    indexes = get_indexes(db)
    print(f"Baseline Indexes count: {len(indexes)}")
    for idx in indexes:
        print(f"  Table: {idx['table']:<20} Index: {idx['index']:<30} Def: {idx['definition']}")
        
    user = db.query(UserModel).first()
    if not user:
        print("Error: No test user found.")
        return
        
    user_id = str(user.user_id)
    
    results = {
        "baseline_counts": {
            "inspections": insp_count,
            "captures": cap_count,
            "report_snapshots": rep_count
        },
        "indexes": indexes,
        "measurements": {}
    }
    
    # Measure baseline
    measure_queries(db, user_id, results["measurements"], "baseline")
    
    # 2. Bounded scaling to 5,000
    print("\n--- 2. Inserting to 5,000 inspections ---")
    target_5k = 5000
    to_insert_5k = target_5k - insp_count
    inserted_ids = []
    
    t0 = time.perf_counter()
    if to_insert_5k > 0:
        print(f"Inserting {to_insert_5k} inspections...")
        # Bulk raw SQL insert to make it extremely fast
        # Let's insert in chunks
        chunk_size = 1000
        for i in range(0, to_insert_5k, chunk_size):
            current_chunk = min(chunk_size, to_insert_5k - i)
            values_list = []
            for _ in range(current_chunk):
                insp_id = str(uuid.uuid4())
                inserted_ids.append(insp_id)
                values_list.append(
                    f"('{insp_id}', '2026-08-26', 'GENERIC_RETAIL_PACKAGE', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'plan_software_1', 'INCOMPLETE_INSPECTION', 'INSUFFICIENT_FOR_ABSENCE_EVALUATION', 'DRAFT', '{user_id}', NOW(), NOW())"
                )
            query_str = f"""
                INSERT INTO inspections (
                    inspection_id, reference_date, product_category, product_origin, regulatory_product_class,
                    date_regulatory_regime, date_package_exemption, is_electronic, package_structure,
                    alcohol_context, capture_plan_id, capture_status, evidence_sufficiency,
                    lifecycle_status, created_by_user_id, created_at, updated_at
                ) VALUES {', '.join(values_list)}
            """
            db.execute(text(query_str))
        db.commit()
    t_setup_5k = time.perf_counter() - t0
    print(f"Setup 5k completed in {t_setup_5k:.2f} seconds.")
    
    measure_queries(db, user_id, results["measurements"], "5000_inspections")
    
    # 3. Bounded scaling to 10,000
    print("\n--- 3. Inserting to 10,000 inspections ---")
    target_10k = 10000
    current_count = db.execute(text("SELECT count(*) FROM inspections")).scalar()
    to_insert_10k = target_10k - current_count
    
    t0 = time.perf_counter()
    if to_insert_10k > 0:
        print(f"Inserting {to_insert_10k} inspections...")
        chunk_size = 1000
        for i in range(0, to_insert_10k, chunk_size):
            current_chunk = min(chunk_size, to_insert_10k - i)
            values_list = []
            for _ in range(current_chunk):
                insp_id = str(uuid.uuid4())
                inserted_ids.append(insp_id)
                values_list.append(
                    f"('{insp_id}', '2026-08-26', 'GENERIC_RETAIL_PACKAGE', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'plan_software_1', 'INCOMPLETE_INSPECTION', 'INSUFFICIENT_FOR_ABSENCE_EVALUATION', 'DRAFT', '{user_id}', NOW(), NOW())"
                )
            query_str = f"""
                INSERT INTO inspections (
                    inspection_id, reference_date, product_category, product_origin, regulatory_product_class,
                    date_regulatory_regime, date_package_exemption, is_electronic, package_structure,
                    alcohol_context, capture_plan_id, capture_status, evidence_sufficiency,
                    lifecycle_status, created_by_user_id, created_at, updated_at
                ) VALUES {', '.join(values_list)}
            """
            db.execute(text(query_str))
        db.commit()
    t_setup_10k = time.perf_counter() - t0
    print(f"Setup 10k completed in {t_setup_10k:.2f} seconds.")
    
    measure_queries(db, user_id, results["measurements"], "10000_inspections")
    
    # 4. Clean up benchmark rows
    print("\n--- 4. Data Cleanup ---")
    t0 = time.perf_counter()
    if inserted_ids:
        # Delete inserted inspections in chunks to avoid lock issues
        chunk_size = 1000
        for i in range(0, len(inserted_ids), chunk_size):
            chunk = inserted_ids[i:i+chunk_size]
            db.execute(text("DELETE FROM inspections WHERE inspection_id IN :ids"), {"ids": tuple(chunk)})
        db.commit()
    t_cleanup = time.perf_counter() - t0
    print(f"Cleanup completed in {t_cleanup:.2f} seconds.")
    
    # Final check of row counts
    final_insp, final_cap, final_rep = get_row_counts(db)
    print(f"Final rows: Inspections={final_insp}, Captures={final_cap}, Report Snapshots={final_rep}")
    
    results["cleanup"] = {
        "final_inspections": final_insp,
        "final_captures": final_cap,
        "final_report_snapshots": final_rep,
        "cleanup_sec": t_cleanup
    }
    
    # Write output to results
    output_path = "/app/benchmark/results/db_scale_baseline.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDatabase scale baseline saved to {output_path}")
    
    db.close()

if __name__ == '__main__':
    run_scale_validation()
