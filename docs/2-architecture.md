# DRISHTI — System Architecture

## 1. Architecture summary

DRISHTI is a React single-page application backed by a FastAPI service, PostgreSQL persistence, and MinIO object storage. Capture analysis combines OpenCV image checks, PaddleOCR, optional Gemini contextual vision, controlled hybrid reconciliation, applicability/evidence-sufficiency evaluation, and deterministic regulatory rules. Final conclusions remain officer-controlled.

```text
Desktop / mobile browser
        │ HTTPS/HTTP + bearer JWT
        ▼
React portal ─────────────── IndexedDB pending-capture queue
        │ REST /api
        ▼
FastAPI
  ├─ Authentication and ownership authorization
  ├─ Capture validation and OpenCV image quality
  ├─ PaddleOCR (sole OCR engine)
  ├─ Gemini contextual vision (optional, advisory)
  ├─ Hybrid evidence reconciliation
  ├─ Applicability and evidence sufficiency
  ├─ Deterministic Legal Metrology / scoped FSSAI rules
  ├─ Officer review, corrections, lifecycle control
  ├─ Grounded legal-provision retrieval
  └─ PDF, DOCX, and evidence-package reporting
        │                         │
        ▼                         ▼
PostgreSQL                    MinIO
inspection state, users,      original capture objects
audit/report snapshots,
approved legal corpus
```

## 2. End-to-end capture transaction

For each submitted capture, the backend performs the implemented pipeline in this order:

1. Authenticate and authorize the officer against the inspection.
2. Validate the upload and decode the image.
3. Calculate integrity metadata, including SHA-256.
4. Run image-quality evaluation.
5. Run PaddleOCR and retain text, confidence, and coordinates.
6. Store the original object in MinIO.
7. Extract normalized declaration candidates.
8. When enabled, send the image to the configured Gemini contextual-vision provider.
9. Validate provider JSON locally and reconcile grounded evidence.
10. Aggregate candidates across captures.
11. Evaluate applicability, evidence sufficiency, deterministic rules, and clarifications.
12. Commit the capture database record and updated inspection state together.
13. If database persistence fails, remove the newly stored object so storage and inspection state do not diverge.

The image bytes, not previously stored OCR text, are the input to contextual vision. Provider failures are recorded explicitly; they do not create fabricated candidates or trigger an alternate OCR engine/provider/model.

## 3. Frontend

### Technology and structure

- React 19 and React Router
- Vite build tooling
- Tailwind CSS and project-level portal styles
- Axios for API calls
- Recharts for implemented dashboard visualization
- Lucide React icons

Primary source areas:

```text
frontend/src/
├── App.jsx                    # Authenticated shell and primary navigation
├── components/
│   ├── auth/                  # Sign-in and registration portal
│   ├── inspection/            # Capture, package information, workflow UI
│   └── ocr/                   # Evidence image and OCR presentation
├── pages/
│   ├── Dashboard.jsx
│   ├── MultiViewInspection.jsx
│   ├── PrepareCase.jsx
│   ├── InspectionHistory.jsx
│   └── RuleLibrary.jsx
└── services/
    ├── api.js                 # Dynamic API origin and authenticated requests
    ├── pendingCaptureStore.js # IndexedDB durable device queue
    └── sessionState.js        # Resumable workspace/inspection state
```

The default API base is derived from the browser page hostname and backend port. The frontend never receives MinIO credentials or raw object-store URLs; it loads stored images from the authenticated inspection capture endpoint.

### Mobile capture durability

The capture input requests the environment-facing camera where supported. A selected photograph is written to IndexedDB and considered durably stored only after the IndexedDB transaction completes. Upload retries operate from that durable local record. Navigation warnings are limited to a photograph that has not yet been durably stored on the device.

Active workspace and inspection identifiers are restored across ordinary camera/browser suspension. Server state remains the authority after reconnect.

## 4. Backend

### Technology and layers

- FastAPI and Pydantic for the HTTP boundary and validation
- SQLAlchemy 2 and Alembic for PostgreSQL persistence and migrations
- Service modules for OCR, quality, contextual vision, reconciliation, rules, review, storage, retrieval, and reports
- JWT authentication and Argon2id password hashing

```text
backend/app/
├── api/routes/       # HTTP routing and authorization boundary
├── core/             # Configuration, security, CORS, shared setup
├── models/           # SQLAlchemy models
├── schemas/          # API, domain, report, and provider schemas
├── services/         # Pipeline and reporting services
└── main.py           # FastAPI application composition
```

### Implemented API groups

| Area | Implemented routes |
|---|---|
| Health | `GET /api/health` |
| Authentication | register, login, current user, Admin user management |
| OCR diagnostic | `POST /api/ocr/analyze` |
| Inspections | list, create, detail, context update, capture, workflow, clarifications |
| Officer review | package-information review and declaration corrections |
| Lifecycle | finalize inspection |
| Images | authenticated `GET /api/inspections/{inspection_id}/captures/{capture_id}/image` |
| Reports | structured report, PDF, DOCX, evidence package |
| Dashboard | `GET /api/dashboard` |
| Legal help | rule list, grounded explanation, Admin corpus reindex |

This list describes route families, not a separate public integration contract. The FastAPI-generated API documentation is the source for exact request and response schemas.

## 5. Image validation, quality, and OCR

The upload path validates accepted content, file size, image decoding, dimensions, and integrity. OpenCV produces quality observations used to reject unusable content or require review where image conditions undermine reliable extraction.

PaddleOCR is the sole OCR engine. Its output includes recognized text, confidence, and coordinates tied to the source capture. Empty or low-confidence OCR is represented explicitly; DRISHTI does not silently invoke Tesseract, EasyOCR, a cloud OCR service, or hidden text reconstruction.

OpenCV and OCR observations support evidence handling. They do not independently determine legal compliance.

## 6. Contextual vision and structured output

`GeminiPackageReader` uses the Google `generateContent` endpoint with the configured Gemini model. It sends actual image bytes with the correct MIME type, a controlled prompt, and a shallow Gemini-facing response schema. Returned JSON is then validated through the stricter local Pydantic models.

The provider may observe fields such as brand, product, quantity, price, responsible-party text, dates, consumer care, ingredients, allergens, FSSAI licence, nutrition, and veg/non-veg mark. An observation is not automatically authoritative.

Provider statuses cover disabled configuration, missing credentials, timeout, quota, invalid response, and HTTP/provider failure. The key and base64 image data are never exposed through client output or diagnostic logs.

Gemini must not:

- make a compliance decision;
- infer legal absence;
- turn an address into country of origin;
- invent declarations or citations;
- override PaddleOCR provenance, deterministic rules, or officer review;
- cause automatic switching to another provider/model.

## 7. Hybrid evidence reconciliation

Reconciliation compares PaddleOCR-derived candidates with Gemini observations while retaining provider evidence and conflicts. It can promote an explicit, grounded observation under controlled rules, but unsupported inferences remain in the advisory audit record and are not inserted into the authoritative candidate set.

The reconciler distinguishes:

- provider agreement;
- complementary observations;
- conflicting values requiring review;
- unsupported inference;
- unavailable advisory provider, with PaddleOCR path preserved.

This is evidence reconciliation, not AI voting. Deterministic rule services consume supported candidates and confirmed context, not raw Gemini authority.

## 8. Applicability, sufficiency, and rules

Applicability determines whether a rule belongs to the confirmed inspection context. Evidence sufficiency determines whether the captures and supporting observations can sustain that rule's evaluation. These are separate from capture-workflow completeness.

The deterministic services implement Legal Metrology checks and a scoped set of food-label checks, including supported ingredients, nutrition, veg/non-veg, licence, allergen, and related declarations. Visual presentation rules are conservative: a FRONT image is not automatically a principal display panel, and pixel measurements do not establish physical size without calibration.

Per-rule results are:

- `PASS`
- `FAIL`
- `REVIEW_REQUIRED`
- `NOT_APPLICABLE`

Each result carries a deterministic reason and, where relevant, rule/legal references and evidence linkage.

## 9. Officer review and inspection lifecycle

Lifecycle states are `DRAFT`, `IN_PROGRESS`, `READY_FOR_REVIEW`, and `FINALIZED`.

The officer confirms package information before finalization. A declaration correction is an append-only overlay that preserves the first machine-observed value and all subsequent corrections. Applying a correction invalidates earlier review confirmation, reruns deterministic assessment, and invalidates only mutable draft report state. Finalized report snapshots remain immutable.

Finalization requires the implemented capture/analysis and current officer-review prerequisites. It locks inspection mutation and creates the durable report snapshot. It does not convert review/fail results into pass and does not automatically submit anything externally.

## 10. Persistence and storage

PostgreSQL stores authenticated users, inspection sessions, captures and audit state, corrections, report snapshots, dashboard/history data, and the approved legal-help corpus. Alembic manages schema evolution.

MinIO is the configured durable capture-object store. Object keys remain server-side. Client image access resolves legacy and current server-side keys through an authenticated inspection-authorized endpoint. Capture-state persistence is coordinated with object cleanup on failure.

Any in-process session cache is transient and is not a durable replacement for PostgreSQL or MinIO.

## 11. Reports

The report service builds a structured snapshot from the inspection state and provider/rule evidence. PDF is rendered with ReportLab and DOCX with python-docx; the evidence package supports officer-controlled downstream use.

Reports include inspection/capture context, workflow completeness, overall disposition, result counts, declaration information, deterministic findings, legal references, evidence images/crops where supported, provider conflicts/review, and officer/finalization metadata.

The disposition is derived from persisted findings and workflow state. `FINALIZED` means immutable and officer-approved for report generation; it is not synonymous with compliant.

## 12. Grounded legal-provision help

The legal-help service retrieves from an approved PostgreSQL corpus using local term weighting. It returns source-grounded explanatory material for supported Legal Metrology and food-label domains, or declines when sufficient authoritative material is not available. It does not generate a legal conclusion, alter a finding, or silently search unapproved sources.

## 13. Security boundaries

- Bearer JWT authentication is required for protected routes.
- Passwords are Argon2id hashes.
- Inspection ownership and Admin authorization are enforced server-side.
- CORS uses explicit approved origins with credentials; wildcard credentialed origins are prohibited.
- Storage credentials, API keys, server-side object keys, and base64 payloads are not client-facing.
- Secrets belong in local environment configuration and must not be committed.
- External handoff remains an explicit officer action.

## 14. Deployment

Docker Compose runs PostgreSQL, MinIO, the FastAPI backend, and the frontend. Database migrations must be current before relying on a deployment. Live Gemini, PostgreSQL, and MinIO validation depends on their respective configured services; infrastructure failures must be distinguished from code-test failures.
