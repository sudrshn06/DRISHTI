# DRISHTI Backup & Restore Operations Manual

## 1. What Must Be Backed Up
1. **PostgreSQL Database (`drishti`)**: Stores users, inspection metadata, captures metadata, report snapshots, and compliance results.
2. **MinIO Object Storage (`drishti-captures`)**: Stores original, immutable image files (evidence objects) using extension-neutral deterministic keys.

---

## 2. PostgreSQL Backup/Restore Procedure

### Backup (Native pg_dump)
Run from the host environment:
```bash
docker-compose exec -T db pg_dump -U drishti drishti > backend/benchmark/backups/drishti_backup.sql
```

### Restore (Isolated Database Validation)
1. Create a clean isolated database:
   ```bash
   docker-compose exec -T db psql -U drishti -d postgres -c "CREATE DATABASE drishti_restore_validation;"
   ```
2. Restore the SQL dump into the isolated database:
   ```bash
   cmd /c "docker-compose exec -T db psql -U drishti -d drishti_restore_validation < backend\benchmark\backups\drishti_backup.sql"
   ```

---

## 3. MinIO Backup/Restore Procedure

### Backup
Download all objects from the live bucket using standard S3/MinIO APIs or replication:
* Bucket: `drishti-captures`
* Save as local binaries matching original object keys (e.g. `inspections/{inspection_id}/captures/{capture_id}/source`).

### Restore
1. Upload backed-up objects to an isolated prefix or temporary bucket (e.g. `drishti-restore-temp` or `restore_validation_temp/`).
2. Do not modify or overwrite live production objects.

---

## 4. Integrity Verification Checklist
* [ ] **Row Count Match**: Compare row counts in `users`, `inspections`, `captures`, and `report_snapshots` tables between live and restored databases.
* [ ] **Key Presence & Byte Identity**: Retrieve selected restored objects from MinIO and check that sizes match original sizes.
* [ ] **Cryptographic Hash Matching**: Calculate the SHA-256 hash of restored bytes and verify that it matches the `image_sha256` value stored in the database.
* [ ] **Tamper Detection (Negative Test)**: Append `\x00` to a restored evidence object. Recompute SHA-256 and confirm that a hash mismatch is successfully triggered.
