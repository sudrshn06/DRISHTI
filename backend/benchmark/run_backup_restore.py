import os
import sys
import time
import json
import hashlib
import io
import shutil
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add /app to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.services.storage_adapter import default_storage_adapter

def get_db_counts(db_url: str):
    engine = create_engine(db_url)
    with engine.connect() as conn:
        users = conn.execute(text("SELECT count(*) FROM users")).scalar()
        inspections = conn.execute(text("SELECT count(*) FROM inspections")).scalar()
        captures = conn.execute(text("SELECT count(*) FROM captures")).scalar()
        snapshots = conn.execute(text("SELECT count(*) FROM report_snapshots")).scalar()
    engine.dispose()
    return {
        "users": users,
        "inspections": inspections,
        "captures": captures,
        "report_snapshots": snapshots
    }

def canonical_hash_json(data: dict) -> str:
    # Sort keys to ensure deterministic serialization
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def run_verification():
    print("Starting Phase 9F Backup & Restore validation...")
    results = {}
    
    live_snap_hash = ""
    restored_snap_hash = ""
    
    live_url = settings.database_url
    restore_url = live_url.rsplit("/", 1)[0] + "/drishti_restore_validation"
    
    # 1. Row counts comparison
    try:
        live_counts = get_db_counts(live_url)
        restore_counts = get_db_counts(restore_url)
        print(f"Live DB Counts: {live_counts}")
        print(f"Restored DB Counts: {restore_counts}")
        db_match = (live_counts == restore_counts)
        results["db_counts_match"] = "PASS" if db_match else "FAIL"
    except Exception as e:
        print(f"Database comparison failed: {e}")
        results["db_counts_match"] = "FAIL"
        
    # 2. Durable Local MinIO Backup
    backup_dir = "/app/benchmark/backups/minio"
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir, ignore_errors=True)
    os.makedirs(backup_dir, exist_ok=True)
    
    try:
        client = default_storage_adapter._get_client()
        live_bucket = default_storage_adapter.bucket_name
        
        objects = list(client.list_objects(live_bucket, recursive=True))
        print(f"Source object count in MinIO: {len(objects)}")
        
        # Save to filesystem
        backup_file_count = 0
        total_bytes = 0
        copy_errors = 0
        
        for obj in objects:
            key = obj.object_name
            if "desktop.ini" in key or ".DS_Store" in key:
                continue
            try:
                response = client.get_object(live_bucket, key)
                data = response.read()
                response.close()
                response.release_conn()
                
                # Write to mirror directory structure
                local_path = os.path.join(backup_dir, key)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(data)
                
                backup_file_count += 1
                total_bytes += len(data)
            except Exception as e:
                print(f"Error copying {key}: {e}")
                copy_errors += 1
                
        print(f"Durable Backup completed. File count={backup_file_count}, Total bytes={total_bytes}, Errors={copy_errors}")
        results["minio_backup_durable"] = "PASS" if (backup_file_count > 0 and copy_errors == 0) else "FAIL"
        
        # 3. Restore from Durable Backup
        restore_prefix = "restore_validation_temp/"
        restored_keys = []
        
        # Read from local filesystem backup
        for root, _, files in os.walk(backup_dir):
            for file in files:
                if file.lower() in ("desktop.ini", ".ds_store"):
                    continue
                local_file_path = os.path.join(root, file)
                # Recover key from local relative path
                rel_path = os.path.relpath(local_file_path, backup_dir)
                key = rel_path.replace(os.path.sep, "/")
                
                try:
                    with open(local_file_path, "rb") as f:
                        file_bytes = f.read()
                        
                    restored_key = restore_prefix + key
                    data_stream = io.BytesIO(file_bytes)
                    client.put_object(
                        bucket_name=live_bucket,
                        object_name=restored_key,
                        data=data_stream,
                        length=len(file_bytes),
                        content_type="image/jpeg"
                    )
                    restored_keys.append(restored_key)
                except Exception as e:
                    print(f"Error restoring local file {local_file_path}: {e}")
                
        print(f"Restored {len(restored_keys)} objects from local filesystem to prefix {restore_prefix}")
        
        # Verify restored objects
        restored_objects = list(client.list_objects(live_bucket, prefix=restore_prefix, recursive=True))
        print(f"Restored count in MinIO: {len(restored_objects)}")
        
        # Verify SHA integrity (DB capture vs local filesystem backup vs restored MinIO)
        # Find a capture in live DB
        live_engine = create_engine(live_url)
        with live_engine.connect() as conn:
            sample_capture = conn.execute(text("SELECT object_key, image_sha256 FROM captures LIMIT 1")).fetchone()
        live_engine.dispose()
        
        sha_triple_match = False
        if sample_capture:
            db_key, db_sha = sample_capture[0], sample_capture[1]
            
            # 1. Local backup hash
            local_backup_file = os.path.join(backup_dir, db_key)
            if os.path.exists(local_backup_file):
                with open(local_backup_file, "rb") as f:
                    backup_bytes = f.read()
                backup_sha = hashlib.sha256(backup_bytes).hexdigest()
                
                # 2. Restored MinIO hash
                restored_key = restore_prefix + db_key
                response = client.get_object(live_bucket, restored_key)
                restored_bytes = response.read()
                response.close()
                response.release_conn()
                restored_sha = hashlib.sha256(restored_bytes).hexdigest()
                
                print(f"Key: {db_key}")
                print(f"  DB SHA256      : {db_sha}")
                print(f"  Backup SHA256  : {backup_sha}")
                print(f"  Restored SHA256: {restored_sha}")
                
                if db_sha == backup_sha == restored_sha:
                    sha_triple_match = True
                    
        results["sha_triple_match"] = "PASS" if sha_triple_match else "FAIL"
        
        # 4. Snapshot semantic equality comparison
        snapshot_match = False
        
        live_engine = create_engine(live_url)
        restore_engine = create_engine(restore_url)
        
        with live_engine.connect() as l_conn, restore_engine.connect() as r_conn:
            # Get a finalized report snapshot
            live_snap = l_conn.execute(text("SELECT snapshot_payload FROM report_snapshots LIMIT 1")).fetchone()
            if live_snap:
                live_payload = live_snap[0]
                restored_snap = r_conn.execute(text("SELECT snapshot_payload FROM report_snapshots LIMIT 1")).fetchone()
                if restored_snap:
                    restored_payload = restored_snap[0]
                    
                    # Canonicalize and hash
                    live_snap_hash = canonical_hash_json(live_payload)
                    restored_snap_hash = canonical_hash_json(restored_payload)
                    
                    print(f"LIVE_SNAPSHOT_HASH    : {live_snap_hash}")
                    print(f"RESTORED_SNAPSHOT_HASH: {restored_snap_hash}")
                    
                    if live_snap_hash == restored_snap_hash:
                        snapshot_match = True
                        print("Snapshot match check: MATCH")
                    else:
                        print("Snapshot match check: MISMATCH")
        
        live_engine.dispose()
        restore_engine.dispose()
        results["snapshot_equality"] = "PASS" if snapshot_match else "FAIL"
        
        # 5. Tamper test on local filesystem backup copy
        tamper_match_fails = False
        if sample_capture:
            local_backup_file = os.path.join(backup_dir, sample_capture[0])
            if os.path.exists(local_backup_file):
                # Copy file and tamper
                tamper_copy_path = local_backup_file + ".tampered"
                shutil.copy2(local_backup_file, tamper_copy_path)
                with open(tamper_copy_path, "ab") as f:
                    f.write(b"\x00") # append byte
                
                with open(tamper_copy_path, "rb") as f:
                    tampered_bytes = f.read()
                tampered_sha = hashlib.sha256(tampered_bytes).hexdigest()
                
                print(f"Original Backup SHA-256: {backup_sha}")
                print(f"Tampered Copy SHA-256  : {tampered_sha}")
                if tampered_sha != backup_sha:
                    tamper_match_fails = True
                    print("Tamper check: Mismatch verified.")
                if os.path.exists(tamper_copy_path):
                    os.remove(tamper_copy_path)
                
        results["tamper_test"] = "PASS" if tamper_match_fails else "FAIL"
        
        # Clean up restored prefix objects
        for r_key in restored_keys:
            try:
                client.remove_object(live_bucket, r_key)
            except:
                pass
        print("Cleaned up restored prefix objects from MinIO.")
        
    except Exception as e:
        print(f"MinIO validation failed: {e}")
        results["minio_backup_durable"] = "FAIL"
        results["sha_triple_match"] = "FAIL"
        results["snapshot_equality"] = "FAIL"
        results["tamper_test"] = "FAIL"
        
    # Write output to validation JSON
    output_path = "/app/benchmark/results/backup_restore_validation.json"
    with open(output_path, "w") as f:
        json.dump({
            "results": results,
            "live_snapshot_hash": live_snap_hash,
            "restored_snapshot_hash": restored_snap_hash
        }, f, indent=2)
        
    print("\n================ FINAL BACKUP & RESTORE VERIFICATION MATRIX ================")
    for key, status in results.items():
        print(f"{key.upper():<40}: {status}")
    print("======================================================================")

if __name__ == '__main__':
    run_verification()
