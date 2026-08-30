import os
import sys
import csv
import json
import time
import io
from datetime import date
from fastapi import UploadFile

# Add /app to sys.path so we can import services
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Import production services directly
from app.services.image_validator import validate_and_decode_image
from app.services.image_quality import assess_image_quality
from app.services.ocr_engine import analyze_image
from app.services.candidate_extractor import extract_candidates
from app.services.compliance_service import orchestrate_compliance

def main():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.csv")
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)
    
    if not os.path.exists(manifest_path):
        print(f"Manifest not found at {manifest_path}")
        sys.exit(1)
        
    records = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
            
    print(f"Loaded {len(records)} benchmark cases from manifest.")
    
    results = []
    total_processed = 0
    successful_count = 0
    failed_count = 0
    non_terminal_quality_warnings = 0
    
    failure_counts = {
        "CAPTURE_QUALITY_FAILURE": 0,
        "OCR_RECOGNITION_FAILURE": 0,
        "EXTRACTION_FAILURE": 0,
        "ASSOCIATION_FAILURE": 0,
        "NORMALIZATION_FAILURE": 0,
        "CONTEXT_REQUIRED": 0,
        "EVIDENCE_INSUFFICIENT": 0,
        "LEGAL_RULE_FAILURE": 0,
        "SYSTEM_ERROR": 0,
        "NO_FAILURE": 0
    }
    
    ocr_durations = []
    pipeline_durations = []
    
    for row in records:
        pkg_id = row.get("package_id")
        img_id = row.get("image_id")
        view = row.get("view")
        img_rel_path = row.get("image_path")
        category = row.get("product_category", "GENERIC_RETAIL_PACKAGE")
        product_class = row.get("regulatory_product_class", "NON_FOOD")
        
        # Absolute path relative to container root (/app)
        app_root = "/app"
        img_abs_path = os.path.abspath(os.path.join(app_root, img_rel_path))
        
        print(f"\nProcessing package: {pkg_id}, image: {img_id}...")
        
        start_pipeline = time.time()
        failure_type = "NO_FAILURE"
        ocr_dur = 0.0
        quality_outcome = "ACCEPTED"
        extracted_families = []
        err_msg = ""
        
        try:
            if not os.path.exists(img_abs_path):
                raise FileNotFoundError(f"Image file not found at path: {img_rel_path}")
                
            with open(img_abs_path, "rb") as img_f:
                file_bytes = img_f.read()
                
            # Create a mock upload file
            mock_file = UploadFile(
                filename=os.path.basename(img_abs_path),
                file=io.BytesIO(file_bytes)
            )
            
            # 1. Image Quality / Decode
            decoded_image, sha256_hash = validate_and_decode_image(mock_file)
            quality_assessment = assess_image_quality(decoded_image)
            quality_outcome = quality_assessment.quality_status
            
            # 2. OCR
            start_ocr = time.time()
            ocr_lines = analyze_image(decoded_image)
            ocr_dur = time.time() - start_ocr
            ocr_durations.append(ocr_dur)
            
            if not ocr_lines:
                failure_type = "OCR_RECOGNITION_FAILURE"
                
            # 3. Extraction
            evidence_map = {str(i): f"ev_{i}" for i in range(len(ocr_lines))}
            candidates = extract_candidates(ocr_lines, evidence_map)
            
            extracted_families = [c.field for c in candidates if c.status in ("DETECTED", "REVIEW_REQUIRED")]
            if not extracted_families and failure_type == "NO_FAILURE":
                failure_type = "EXTRACTION_FAILURE"
                
            # 4. Compliance (orchestrate)
            results_rules = orchestrate_compliance(
                candidates=candidates,
                reference_date=date(2026, 8, 26),
                product_category=category,
                regulatory_category=product_class
            )
            
            if quality_outcome == "RETAKE_RECOMMENDED":
                non_terminal_quality_warnings += 1
                
            successful_count += 1
            
        except Exception as e:
            failed_count += 1
            err_msg = str(e)
            if isinstance(e, FileNotFoundError):
                failure_type = "CAPTURE_QUALITY_FAILURE"
            elif "HTTPException" in type(e).__name__ or "validation" in err_msg.lower():
                failure_type = "CAPTURE_QUALITY_FAILURE"
            else:
                failure_type = "SYSTEM_ERROR"
                
        pipeline_dur = time.time() - start_pipeline
        pipeline_durations.append(pipeline_dur)
        total_processed += 1
        
        failure_counts[failure_type] += 1
        
        results.append({
            "package_id": pkg_id,
            "image_id": img_id,
            "view": view,
            "image_path": img_rel_path,
            "quality_outcome": quality_outcome,
            "ocr_success": "YES" if ocr_dur > 0 else "NO",
            "ocr_duration_sec": round(ocr_dur, 4),
            "extracted_families": ",".join(extracted_families),
            "pipeline_duration_sec": round(pipeline_dur, 4),
            "failure_taxonomy": failure_type,
            "error_message": err_msg
        })
        
    # Calculate stats
    median_ocr = sorted(ocr_durations)[len(ocr_durations)//2] if ocr_durations else 0.0
    median_pipeline = sorted(pipeline_durations)[len(pipeline_durations)//2] if pipeline_durations else 0.0
    
    summary = {
        "total_images_processed": total_processed,
        "successful_processing_count": successful_count,
        "failed_processing_count": failed_count,
        "non_terminal_quality_warning_count": non_terminal_quality_warnings,
        "median_ocr_duration_sec": round(median_ocr, 4),
        "median_pipeline_duration_sec_includes_ocr": round(median_pipeline, 4),
        "failure_category_counts": failure_counts
    }
    
    # Write JSON results
    output_json_path = os.path.join(results_dir, "latest.json")
    with open(output_json_path, "w", encoding="utf-8") as f_json:
        json.dump({
            "note": "pipeline_duration_sec includes image validation, quality metrics, OCR, extraction and legal rules evaluation.",
            "summary": summary,
            "results": results
        }, f_json, indent=2)
        
    # Write CSV results
    output_csv_path = os.path.join(results_dir, "latest.csv")
    with open(output_csv_path, "w", newline="", encoding="utf-8") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow([
            "package_id", "image_id", "view", "image_path", 
            "quality_outcome", "ocr_success", "ocr_duration_sec", 
            "extracted_families", "pipeline_duration_sec", "failure_taxonomy", "error_message"
        ])
        for r in results:
            writer.writerow([
                r["package_id"], r["image_id"], r["view"], r["image_path"],
                r["quality_outcome"], r["ocr_success"], r["ocr_duration_sec"],
                r["extracted_families"], r["pipeline_duration_sec"], r["failure_taxonomy"], r["error_message"]
            ])
            
    print(f"\nBenchmark completed successfully.")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
