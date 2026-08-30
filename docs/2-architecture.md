# DRISHTI — System Architecture

## 1. Architecture Overview

DRISHTI follows a **monolithic layered architecture** with clear separation between frontend, backend API, processing pipeline, rule engine, and data layer.

### Design Principles

- **One implementation per capability** — no fallback engines, no duplicate providers.
- **Explicit failure** — every component reports its own failure state; no silent substitution.
- **Evidence-first** — all compliance decisions trace back to structured evidence with image coordinates.
- **Deterministic evaluation** — legal compliance is decided by a rule engine, not by AI.
- **Version-aware rules** — applicable rules are selected based on product category, package type, and inspection date.

---

## 2. Architecture Diagram

```mermaid
graph TB
    subgraph "Frontend — React / Vite"
        UI["UI Layer<br/>React + Tailwind CSS"]
        ANIM["Animation Layer<br/>Anime.js"]
        RBITS["Selected React Bits<br/>Components"]
        CHARTS["Charts<br/>Recharts"]
    end

    subgraph "Backend — FastAPI"
        API["REST API<br/>FastAPI + Pydantic"]
        AUTH["Auth Module<br/>JWT + RBAC + Argon2id"]
        
        subgraph "Processing Pipeline"
            IQV["Image Quality<br/>Validator"]
            OCR["OCR Engine<br/>PaddleOCR"]
            CV["Computer Vision<br/>OpenCV"]
            DCL["Declaration<br/>Classifier (Deterministic)"]
        end

        subgraph "Legal Compliance"
            RUL["Rule Engine<br/>Deterministic Python"]
            RSEL["Rule Selector<br/>Version-aware"]
        end

        subgraph "Inspection Management"
            INS["Inspection<br/>Service"]
            EVD["Evidence<br/>Service"]
            RPT["Report Generator<br/>ReportLab + python-docx"]
        end
    end

    subgraph "Data Layer"
        DB[("PostgreSQL<br/>SQLAlchemy + Alembic")]
        FS["File Storage<br/>Local filesystem (dev)<br/>MinIO/S3 (prod migration)"]
    end

    UI --> API
    ANIM --> UI
    RBITS --> UI
    CHARTS --> UI
    API --> AUTH
    API --> INS
    INS --> IQV
    IQV --> CV
    INS --> OCR
    OCR --> DCL
    DCL --> EVD
    EVD --> RSEL
    RSEL --> RUL
    INS --> RPT
    INS --> DB
    EVD --> DB
    RUL --> DB
    IQV --> FS
    OCR --> FS
    EVD --> FS
    RPT --> FS
    AUTH --> DB
```

---

## 3. End-to-End Flow

```mermaid
sequenceDiagram
    participant Inspector
    participant Frontend
    participant API
    participant ImageValidator
    participant PaddleOCR
    participant OpenCV
    participant Classifier
    participant RuleEngine
    participant Database
    participant Storage

    Inspector->>Frontend: Create new inspection
    Frontend->>API: POST /api/inspections
    API->>Database: Create inspection record
    API-->>Frontend: Inspection created

    Inspector->>Frontend: Upload panel image
    Frontend->>API: POST /api/inspections/{id}/panels/{panel}/image
    API->>Storage: Store original image
    API->>ImageValidator: Validate image quality
    
    alt Image quality insufficient
        ImageValidator-->>API: IMAGE_RETAKE_REQUIRED
        API-->>Frontend: Rejection with reason
    else Image quality acceptable
        ImageValidator-->>API: Quality OK
        API->>PaddleOCR: Extract text
        
        alt OCR fails
            PaddleOCR-->>API: OCR_PROCESSING_FAILED
            API-->>Frontend: Processing error (Retry available)
        else OCR succeeds
            PaddleOCR-->>API: Text + confidence + polygons
            API->>Classifier: Classify declarations
            API->>Database: Store structured evidence
            API-->>Frontend: Extraction results
        end
    end

    Inspector->>Frontend: Evaluate compliance
    Frontend->>API: POST /api/inspections/{id}/evaluate
    API->>RuleEngine: Select applicable rules
    API->>RuleEngine: Evaluate evidence against rules
    RuleEngine-->>API: Findings (PASS/FAIL/REVIEW per rule)
    API->>Database: Store findings
    API-->>Frontend: Compliance results

    Inspector->>Frontend: Generate report
    Frontend->>API: POST /api/inspections/{id}/reports
    API->>Database: Retrieve inspection + findings + evidence
    API-->>Frontend: PDF/DOCX report
```

---

## 4. Frontend Architecture

### Technology

| Component | Technology |
|-----------|-----------|
| Framework | React 18+ |
| Build Tool | Vite |
| Styling | Tailwind CSS |
| Icons | Lucide React |
| Charts | Recharts |
| Animations | Anime.js |
| UI Components | Selected React Bits components |
| HTTP Client | Axios |
| Routing | React Router |
| State Management | React Context + useReducer |

### Frontend Responsibilities

- Authentication UI (login, session management)
- Dashboard with inspection summaries and metrics
- Inspection creation and product details form
- Guided panel capture interface
- Image upload with quality feedback
- Evidence viewer with bounding-box overlays
- Compliance results display (PASS / FAIL / REVIEW)
- Violation detail with linked evidence
- Report generation trigger and preview
- Inspection history with filtering
- Rule administration interface (RULE_ADMIN role)
- User management interface (ADMIN role)

### Frontend Restrictions

- **Never fabricate** compliance results, confidence values, progress percentages, legal findings, inspection state, or evidence.
- **Never make legal decisions** — all compliance results come from the backend rule engine.
- **Animations must reflect real application state** — no fake progress bars, no simulated processing.

---

## 5. Backend Architecture

### Technology

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Auth | PyJWT + Argon2id (argon2-cffi) |
| OCR | PaddleOCR |
| Computer Vision | OpenCV (opencv-python-headless) |
| Reporting | ReportLab (PDF), python-docx (DOCX) |
| Testing | pytest |

### Backend Layer Structure

```
┌─────────────────────────────────────┐
│           API Layer (Routers)       │  ← HTTP endpoints, request validation
├─────────────────────────────────────┤
│          Service Layer              │  ← Business logic, orchestration
├─────────────────────────────────────┤
│        Processing Pipeline          │  ← Image validation, OCR, CV, classification
├─────────────────────────────────────┤
│          Rule Engine                │  ← Deterministic legal evaluation
├─────────────────────────────────────┤
│         Data Access Layer           │  ← SQLAlchemy models, repositories
├─────────────────────────────────────┤
│       Storage Layer                 │  ← File system / object storage
└─────────────────────────────────────┘
```

### API Structure

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Authenticate user |
| `POST` | `/api/auth/refresh` | Refresh JWT token |
| `GET` | `/api/users/me` | Current user profile |
| `GET` | `/api/inspections` | List inspections (filtered) |
| `POST` | `/api/inspections` | Create new inspection |
| `GET` | `/api/inspections/{id}` | Get inspection details |
| `PUT` | `/api/inspections/{id}` | Update inspection |
| `POST` | `/api/inspections/{id}/panels/{panel}/image` | Upload panel image |
| `GET` | `/api/inspections/{id}/panels` | Get panel statuses |
| `POST` | `/api/inspections/{id}/process` | Trigger OCR/extraction for a panel |
| `POST` | `/api/inspections/{id}/evaluate` | Run rule engine evaluation |
| `GET` | `/api/inspections/{id}/evidence` | Get structured evidence |
| `GET` | `/api/inspections/{id}/findings` | Get compliance findings |
| `POST` | `/api/inspections/{id}/reports` | Generate report (PDF/DOCX) |
| `GET` | `/api/inspections/{id}/reports/{report_id}` | Download report |
| `GET` | `/api/rules` | List regulatory rules |
| `POST` | `/api/rules` | Create rule (RULE_ADMIN) |
| `PUT` | `/api/rules/{id}` | Update rule (RULE_ADMIN) |
| `GET` | `/api/rules/{id}/versions` | Get rule versions |
| `GET` | `/api/dashboard/stats` | Dashboard statistics |
| `GET` | `/api/dashboard/analytics` | Enforcement analytics |
| `POST` | `/api/admin/users` | Create user (ADMIN) |
| `PUT` | `/api/admin/users/{id}` | Update user (ADMIN) |
| `GET` | `/api/admin/users` | List users (ADMIN) |

---

## 6. OCR Architecture

### Engine

**PaddleOCR — sole OCR implementation. No fallback.**

### Pipeline

```
Input Image
    ↓
Preprocessing (OpenCV)
  - orientation correction
  - perspective correction (if applicable)
  - contrast enhancement (if needed)
    ↓
PaddleOCR Detection + Recognition
    ↓
Raw OCR Output
  - detected text
  - confidence score
  - bounding polygon coordinates
    ↓
Post-processing
  - text cleaning
  - coordinate normalization
    ↓
Structured OCR Result
```

### OCR Output Schema

```python
class OCRResult(BaseModel):
    text: str
    confidence: float
    polygon: list[list[float]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    source_image_id: str
    panel: PanelType
    processing_version: str
    processed_at: datetime
```

### Failure Handling

| Scenario | Response |
|----------|----------|
| PaddleOCR crashes | `OCR_PROCESSING_FAILED` — Retry available |
| PaddleOCR returns empty results | Low/no text detected — flag for REVIEW |
| PaddleOCR returns low confidence | Proceed with REVIEW flag on affected declarations |
| PaddleOCR unavailable at startup | `SYSTEM_ERROR` — service cannot start without OCR |

---

## 7. OpenCV Pipeline

### Responsibilities

| Function | Description |
|----------|-------------|
| Image quality assessment | Blur detection (Laplacian variance), glare detection, lighting assessment |
| Preprocessing | Rotation correction, perspective correction, contrast enhancement |
| Package detection | Verify image contains a packaged commodity |
| Panel preprocessing | Crop and prepare individual panel images for OCR |
| ArUco/ChArUco detection | Detect calibration markers for physical measurement |
| Pixel-to-mm calibration | Convert pixel dimensions to physical dimensions using known reference |
| Evidence visualization | Draw bounding boxes and highlights on evidence images |

### Image Quality Validation

```python
class ImageQualityResult(BaseModel):
    is_acceptable: bool
    blur_score: float
    blur_acceptable: bool
    glare_detected: bool
    lighting_acceptable: bool
    contains_package: bool
    rejection_reasons: list[str]
```

---

## 8. Evidence Architecture

### Evidence Object

```python
class Evidence(BaseModel):
    evidence_id: str            # UUID
    inspection_id: str          # FK → Inspection
    image_id: str               # FK → InspectionImage
    panel: PanelType            # FRONT, BACK, LEFT, RIGHT, TOP, BOTTOM
    detected_text: str          # Raw OCR text
    normalized_field: str       # e.g., "mrp", "manufacturer_name"
    normalized_value: str       # e.g., "50.00", "ABC Pvt Ltd"
    confidence: float           # OCR confidence
    polygon: list[list[float]]  # Bounding coordinates
    extraction_method: str      # "paddleocr_v4" etc.
    processing_version: str     # Pipeline version
    created_at: datetime
```

### Evidence Integrity

```
Original Image → SHA-256 hash
     ↓
Evidence Record
  - image_hash
  - inspector_id
  - capture_timestamp
  - processing_version
  - rule_version (at evaluation time)
```

No evidence record may be modified after creation. Corrections create new evidence linked to the original.

---

## 9. Declaration Processing

### Classification Pipeline

```
Raw OCR Results (text + confidence + polygon)
       ↓
Text Normalization
  - whitespace cleanup
  - Unicode normalization
  - common OCR error correction (₹ vs Rs, etc.)
       ↓
Deterministic Declaration Classification
  - regex pattern matching (MRP, dates, quantities)
  - structured parsers for known formats
  - normalization of known field patterns
       ↓
Structured Evidence
  - field: "mrp"
  - value: "50.00"
  - unit: "INR"
  - raw_text: "MRP ₹50.00 incl. of all taxes"
  - confidence: 0.95
  - source_evidence_id: "..."
       ↓
If text cannot be confidently classified:
  → REVIEW_REQUIRED
  or store as unclassified evidence
```

> [!IMPORTANT]
> AI is NOT part of the mandatory classification pipeline. Deterministic methods (regex, pattern matching, structured parsers) are the sole classification implementation. If AI-assisted classification for a specific task is desired later, it must be introduced as a separate, explicitly approved phase after a provider and model have been deliberately selected.

### Classification Methods

| Method | Use Case | `automation_type` |
|--------|----------|-------------------|
| Regex / Pattern Matching | MRP format, date format, quantity format | `DETERMINISTIC` |
| Structured Parsers | Manufacturer name, address, consumer care patterns | `DETERMINISTIC` |
| Manual Review | Unclassifiable text, very low confidence | `MANUAL_REVIEW` |

> [!NOTE]
> `AI_ASSISTED` automation_type exists in the rule schema for future use on specific rules where AI may assist evidence interpretation. However, AI does not make the final legal compliance decision under any circumstances. AI-assisted classification is NOT available in the initial pipeline — it requires an explicit future phase with a selected provider and model.

---

## 10. Deterministic Rule Engine

### Architecture

```
Structured Evidence (declarations)
       ↓
Product Classification (category, package type)
       ↓
Rule Selector
  - filter by product_category
  - filter by package_type
  - filter by effective_date (inspection date within [effective_from, effective_until])
  - filter by active status
       ↓
Applicable Rules
       ↓
Deterministic Validator
  - evaluate each rule against available evidence
  - PASS if evidence satisfies requirement
  - FAIL if evidence clearly violates requirement
  - REVIEW if evidence is ambiguous or insufficient
  - INCOMPLETE if required panel not inspected
       ↓
Findings
  - one finding per evaluated rule
  - linked to supporting evidence
  - includes explanation
```

### Rule Schema

```python
class LegalRule(BaseModel):
    internal_rule_id: str
    legal_citation: str           # e.g., "Rule 6(1)(a)"
    title: str                    # Human-readable title
    requirement: str              # What is required
    field: str                    # Declaration field this rule validates
    applicability: str            # Description of when this rule applies
    package_type: list[str]       # ["retail", "wholesale", "institutional"]
    product_category: list[str]   # ["food", "cosmetics", "general", ...]
    effective_from: date
    effective_until: date | None  # None = still active
    validation_type: str          # "presence", "format", "value_range", "text_match"
    severity: str                 # "mandatory", "advisory"
    source_document: str          # Official document name
    amendment_reference: str | None
    automation_type: str          # "DETERMINISTIC", "AI_ASSISTED", "MANUAL_REVIEW"
    is_active: bool
    version: int
```

### Finding Schema

```python
class Finding(BaseModel):
    finding_id: str
    inspection_id: str
    rule_id: str
    rule_version: int
    result: ResultState           # PASS, FAIL, REVIEW, INCOMPLETE_INSPECTION
    explanation: str
    evidence_ids: list[str]       # References to supporting evidence
    evaluated_at: datetime
    evaluated_by: str             # "rule_engine_v1"
```

### Rule Engine Principles

1. **One authoritative implementation** — all legal evaluation goes through one rule engine module.
2. **No legal logic in controllers or frontend** — rules live in the rule engine and the rule database.
3. **Version-aware** — the rule version effective at the inspection date is used.
4. **Deterministic** — same evidence + same rules = same result. Always.
5. **Explainable** — every finding includes an explanation of why it passed, failed, or requires review.

---

## 11. AI — Optional Later Capability

> [!IMPORTANT]
> AI is NOT part of the mandatory DRISHTI core pipeline. The pipeline from Image → PaddleOCR → Deterministic Classification → Evidence → Rule Engine → PASS/FAIL/REVIEW operates entirely without AI.

### When AI May Be Introduced

AI may be introduced **only** for explicitly defined, separately approved tasks in a later phase, after ONE provider and ONE model have been deliberately selected. Possible tasks include:

| Task | Description |
|------|-------------|
| Finding explanation | Generate human-readable explanations for already-determined legal findings |
| Legal Metrology RAG assistant | Answer regulatory queries using official documents |
| Explicitly approved semantic interpretation | Only for a specific task after provider/model selection |

### AI Policy When Introduced

- **One AI provider** — no fallback provider, no secondary provider.
- **One AI model** — no fallback model, no automatic model switching.
- **No silent retries** through another model or provider.
- **AI does not make PASS/FAIL decisions** — only the deterministic rule engine does.
- **AI does not invent** evidence, citations, requirements, or confidence values.
- **AI does not override** deterministic rule results.
- **AI failure** → `AI_SERVICE_UNAVAILABLE` → preserve state → log error → display Retry.

### AI MUST NOT

- Decide PASS / FAIL
- Invent legal requirements or citations
- Fabricate evidence or OCR content
- Fabricate confidence values
- Override deterministic rule engine results

### Architecture Separation

AI features (when introduced) must be architecturally separate from the compliance pipeline. A failure of an AI feature must not affect the deterministic inspection result.

---

## 12. Database Architecture

### Technology

- **PostgreSQL** — primary database
- **SQLAlchemy 2.0** — ORM
- **Alembic** — migrations

### Core Tables

```mermaid
erDiagram
    User {
        uuid id PK
        string username
        string email
        string password_hash
        string role
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    Inspection {
        uuid id PK
        uuid inspector_id FK
        string status
        string product_name
        string product_category
        string package_type
        string brand
        string batch_number
        string location
        text notes
        datetime inspection_date
        datetime created_at
        datetime updated_at
    }

    InspectionPanel {
        uuid id PK
        uuid inspection_id FK
        string panel_type
        string status
        datetime created_at
    }

    InspectionImage {
        uuid id PK
        uuid inspection_id FK
        uuid panel_id FK
        string panel_type
        string file_path
        string file_hash
        int file_size
        string mime_type
        float blur_score
        boolean quality_acceptable
        datetime captured_at
    }

    Evidence {
        uuid id PK
        uuid inspection_id FK
        uuid image_id FK
        string panel_type
        string detected_text
        string normalized_field
        string normalized_value
        float confidence
        json polygon
        string extraction_method
        string processing_version
        datetime created_at
    }

    LegalRule {
        uuid id PK
        string internal_rule_id
        string legal_citation
        string title
        text requirement
        string field
        json package_type
        json product_category
        date effective_from
        date effective_until
        string validation_type
        string severity
        string automation_type
        boolean is_active
        int version
        string source_document
        string amendment_reference
        datetime created_at
    }

    Finding {
        uuid id PK
        uuid inspection_id FK
        uuid rule_id FK
        int rule_version
        string result
        text explanation
        json evidence_ids
        datetime evaluated_at
        string evaluated_by
    }

    Report {
        uuid id PK
        uuid inspection_id FK
        string format
        string file_path
        string file_hash
        datetime generated_at
        string generated_by
    }

    User ||--o{ Inspection : creates
    Inspection ||--o{ InspectionPanel : has
    Inspection ||--o{ InspectionImage : contains
    InspectionPanel ||--o{ InspectionImage : captures
    InspectionImage ||--o{ Evidence : produces
    Inspection ||--o{ Evidence : contains
    Inspection ||--o{ Finding : evaluates
    LegalRule ||--o{ Finding : applies
    Inspection ||--o{ Report : generates
```

---

## 13. Storage Architecture

### Initial Development

- **Local filesystem** for image and report storage.
- This is the sole active storage implementation during development.
- Organized by inspection ID:

```
/storage/
  /inspections/
    /{inspection_id}/
      /images/
        /front_001.jpg
        /back_001.jpg
      /evidence/
        /front_001_annotated.jpg
      /reports/
        /report_001.pdf
        /report_001.docx
```

### Production Migration

> [!IMPORTANT]
> Migration to MinIO / S3-compatible object storage is a **deployment-phase change**, not a runtime fallback. There must be only ONE configured active storage implementation at runtime. The system does NOT automatically switch between local storage and MinIO.

- When migrating to production, configure **MinIO / S3-compatible object storage**.
- Same logical structure, accessed via object storage API.
- Presigned URLs for frontend image access.
- Local filesystem and MinIO are not used simultaneously at runtime.

---

## 14. Authentication and Authorization

### Authentication

- **JWT tokens** with access and refresh token pattern.
- Access token: short-lived (15–30 minutes).
- Refresh token: longer-lived (7 days), stored securely.
- **Argon2id** for password hashing (via `argon2-cffi`).

### Authorization

- **RBAC** enforced server-side on every endpoint.
- Role checked via JWT claims + database verification.
- Frontend role claims are **never trusted** — authorization is always server-side.

### Role Permissions Matrix

| Endpoint | INSPECTOR | SUPERVISOR | ADMIN | RULE_ADMIN |
|----------|-----------|------------|-------|------------|
| Create inspection | ✅ | ✅ | ❌ | ❌ |
| View own inspections | ✅ | ✅ | ❌ | ❌ |
| View all inspections | ❌ | ✅ | ❌ | ❌ |
| Approve/reopen findings | ❌ | ✅ | ❌ | ❌ |
| View analytics | ❌ | ✅ | ✅ | ❌ |
| Manage users | ❌ | ❌ | ✅ | ❌ |
| Manage rules | ❌ | ❌ | ❌ | ✅ |
| View rules | ✅ | ✅ | ✅ | ✅ |

---

## 15. Reporting Architecture

### Technology

- **ReportLab** — PDF generation
- **python-docx** — DOCX generation

### Report Contents

- Inspection metadata (inspector, date, location, product)
- Product details and classification
- Panel capture summary
- Findings table (rule, citation, result, explanation)
- Evidence references with image thumbnails
- Overall compliance status
- Legal disclaimers
- Signature/approval section (if applicable)

### Report Styles

Reports should follow an official government inspection report format — professional, structured, and formal.

---

## 16. Project Folder Structure

```
DRISHTI/
├── docs/
│   ├── 1-product.md
│   ├── 2-architecture.md
│   ├── 3-rules.md
│   ├── 4-phases.md
│   └── 5-design.md
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── components/
│   │   │   ├── common/           # Shared UI components
│   │   │   ├── inspection/       # Inspection workflow components
│   │   │   ├── evidence/         # Evidence viewer, bounding boxes
│   │   │   ├── dashboard/        # Dashboard widgets
│   │   │   ├── rules/            # Rule administration
│   │   │   └── reports/          # Report preview/download
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── NewInspection.jsx
│   │   │   ├── InspectionDetail.jsx
│   │   │   ├── InspectionHistory.jsx
│   │   │   ├── RuleAdmin.jsx
│   │   │   └── UserManagement.jsx
│   │   ├── hooks/                # Custom React hooks
│   │   ├── services/             # API client functions
│   │   ├── store/                # State management
│   │   ├── utils/                # Utility functions
│   │   ├── animations/           # Anime.js animation definitions
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── auth.py
│   │   │   │   ├── inspections.py
│   │   │   │   ├── evidence.py
│   │   │   │   ├── rules.py
│   │   │   │   ├── reports.py
│   │   │   │   ├── dashboard.py
│   │   │   │   └── admin.py
│   │   │   └── dependencies.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── errors.py
│   │   ├── models/               # SQLAlchemy models
│   │   │   ├── user.py
│   │   │   ├── inspection.py
│   │   │   ├── evidence.py
│   │   │   ├── rule.py
│   │   │   ├── finding.py
│   │   │   └── report.py
│   │   ├── schemas/              # Pydantic schemas
│   │   │   ├── auth.py
│   │   │   ├── inspection.py
│   │   │   ├── evidence.py
│   │   │   ├── rule.py
│   │   │   ├── finding.py
│   │   │   └── report.py
│   │   ├── services/             # Business logic
│   │   │   ├── inspection_service.py
│   │   │   ├── evidence_service.py
│   │   │   ├── rule_service.py
│   │   │   └── report_service.py
│   │   ├── processing/           # Image/OCR/CV pipeline
│   │   │   ├── image_validator.py
│   │   │   ├── ocr_engine.py
│   │   │   ├── cv_pipeline.py
│   │   │   └── declaration_classifier.py
│   │   ├── engine/               # Legal rule engine
│   │   │   ├── rule_engine.py
│   │   │   ├── rule_selector.py
│   │   │   └── validators/
│   │   │       ├── base.py
│   │   │       ├── presence.py
│   │   │       ├── format.py
│   │   │       └── value_range.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   └── main.py
│   ├── alembic/
│   │   ├── versions/
│   │   └── env.py
│   ├── alembic.ini
│   ├── requirements.txt
│   └── pytest.ini
│
├── tests/
│   ├── backend/
│   │   ├── test_ocr.py
│   │   ├── test_image_validator.py
│   │   ├── test_rule_engine.py
│   │   ├── test_declaration_classifier.py
│   │   ├── test_api_inspections.py
│   │   └── test_api_auth.py
│   └── corpus/                   # Validation corpus
│       ├── valid/
│       ├── invalid/
│       └── labels.json
│
├── storage/                      # Local file storage (dev)
│
├── docker-compose.yml
├── Dockerfile.frontend
├── Dockerfile.backend
├── .env.example
├── .gitignore
└── README.md
```

---

## 17. Important Files

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI application entry point |
| `backend/app/core/config.py` | Environment configuration (Pydantic Settings) |
| `backend/app/core/security.py` | JWT + Argon2id + RBAC utilities |
| `backend/app/core/errors.py` | Structured error codes and exception handlers |
| `backend/app/processing/ocr_engine.py` | PaddleOCR wrapper — sole OCR implementation |
| `backend/app/processing/cv_pipeline.py` | OpenCV image processing pipeline |
| `backend/app/processing/image_validator.py` | Image quality validation |
| `backend/app/processing/declaration_classifier.py` | OCR text → declaration classification |
| `backend/app/engine/rule_engine.py` | Deterministic legal rule evaluation |
| `backend/app/engine/rule_selector.py` | Version-aware rule selection |
| `frontend/src/animations/` | Anime.js animation definitions |
| `docker-compose.yml` | Docker Compose for full stack |

---

## 18. Environment Variables

```env
# === Application ===
APP_ENV=development
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000

# === Database ===
DATABASE_URL=postgresql://drishti:password@localhost:5432/drishti
DATABASE_POOL_SIZE=10

# === Authentication ===
JWT_SECRET_KEY=<generate-secure-random-key>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# === Storage ===
STORAGE_TYPE=local
STORAGE_LOCAL_PATH=./storage
# STORAGE_S3_ENDPOINT=http://localhost:9000
# STORAGE_S3_ACCESS_KEY=
# STORAGE_S3_SECRET_KEY=
# STORAGE_S3_BUCKET=drishti

# === OCR ===
PADDLEOCR_LANG=en
PADDLEOCR_USE_GPU=false

# === AI (when introduced) ===
# AI_PROVIDER=<selected-provider>
# AI_API_KEY=<key>
# AI_MODEL=<model-name>

# === Upload Limits ===
MAX_UPLOAD_SIZE_MB=20
ALLOWED_MIME_TYPES=image/jpeg,image/png

# === Frontend (Vite) ===
VITE_API_BASE_URL=http://localhost:8000/api
```

> [!CAUTION]
> Never commit actual secrets. Use `.env.example` with placeholder values only. Actual secrets must be managed via environment variables or a secret manager.

---

## 19. Tech Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18+ | UI framework |
| Build | Vite | Frontend build tool |
| Styling | Tailwind CSS | Utility-first CSS |
| Icons | Lucide React | Icon library |
| Charts | Recharts | Dashboard charts |
| Animations | Anime.js | Workflow animations |
| UI Components | React Bits (selected) | Specialized UI components |
| HTTP Client | Axios | Frontend API communication (sole HTTP client) |
| Routing | React Router | Frontend routing |
| State Management | React Context + useReducer | Frontend state (sole state library) |
| Backend | FastAPI | REST API |
| Validation | Pydantic v2 | Request/response validation |
| ORM | SQLAlchemy 2.0 | Database ORM |
| Migrations | Alembic | Schema migrations |
| Database | PostgreSQL | Primary database |
| OCR | PaddleOCR ONLY | Text extraction (sole engine — no fallback) |
| Computer Vision | OpenCV | Image processing |
| Auth | PyJWT + argon2-cffi | Authentication |
| PDF | ReportLab | PDF report generation |
| DOCX | python-docx | DOCX report generation |
| Testing | pytest | Backend tests |
| Deployment | Docker + Docker Compose | Containerization |
| Storage (dev) | Local filesystem | File storage during development |
| Storage (prod migration) | MinIO / S3-compatible | Object storage — deployment-phase migration only |

---

## 20. Docker Deployment

### docker-compose.yml Structure

```yaml
services:
  frontend:
    build: ./Dockerfile.frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  backend:
    build: ./Dockerfile.backend
    ports:
      - "8000:8000"
    depends_on:
      - db
    env_file:
      - .env
    volumes:
      - ./storage:/app/storage

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: drishti
      POSTGRES_USER: drishti
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

### Deployment Notes

- Single `docker-compose.yml` for the full stack.
- PostgreSQL runs as a Docker service.
- Backend mounts local storage volume for development.
- No Kubernetes, no Redis, no Celery, no Kafka unless explicitly required later.
