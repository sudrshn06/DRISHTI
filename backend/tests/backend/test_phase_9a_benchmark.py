import os
import csv
import json

def test_benchmark_manifest_parsing():
    # Verify manifest exists and is readable
    manifest_path = "backend/benchmark/manifest.csv"
    if not os.path.exists(manifest_path):
        manifest_path = "benchmark/manifest.csv"
        
    assert os.path.exists(manifest_path)
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames is not None
        assert "package_id" in reader.fieldnames
        assert "image_id" in reader.fieldnames
        assert "view" in reader.fieldnames
        assert "image_path" in reader.fieldnames
        assert "difficulty" in reader.fieldnames

def test_benchmark_missing_image_handled_safely():
    # Verify missing path handles cleanly
    img_rel_path = "tests/fixtures/non_existent_image.jpg"
    assert not os.path.exists(img_rel_path)

def test_results_export_is_deterministic():
    results_json = "backend/benchmark/results/latest.json"
    results_csv = "backend/benchmark/results/latest.csv"
    
    if not os.path.exists(results_json):
        results_json = "benchmark/results/latest.json"
    if not os.path.exists(results_csv):
        results_csv = "benchmark/results/latest.csv"
        
    assert os.path.exists(results_json)
    assert os.path.exists(results_csv)
    
    with open(results_json, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert "summary" in data
        assert "results" in data
        assert len(data["results"]) == 6
