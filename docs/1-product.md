# DRISHTI — Product Definition

## 1. Name

**DRISHTI** — Software System to Check Compliance of Packaged Commodities under the Legal Metrology (Packaged Commodities) Rules, 2011 by Scanning Products, Images and Labels.

**SIH Reference:** SIH26034

---

## 2. Problem Statement

Legal Metrology inspectors currently verify packaged commodity compliance through manual visual inspection. This process is:

- **Slow** — Each product requires reading multiple labels across multiple surfaces.
- **Error-prone** — Human inspectors miss declarations, misread values, or apply outdated rules.
- **Inconsistent** — Different inspectors apply different interpretations of the same legal requirement.
- **Undocumented** — Inspection evidence is rarely preserved in a structured, auditable form.
- **Unscalable** — Manual inspection cannot keep pace with the volume of packaged commodities in the market.

There is no standardised software system that converts package images into structured regulatory evidence and evaluates that evidence against applicable Legal Metrology requirements using deterministic rules.

---

## 3. Background

The **Legal Metrology Act, 2009** and the **Legal Metrology (Packaged Commodities) Rules, 2011** mandate that pre-packaged commodities sold in India carry specific declarations on their labels. These include the product name, manufacturer details, net quantity, MRP, date of manufacture/packing, consumer care information, and country of origin (where applicable).

Enforcement is carried out by Legal Metrology inspectors who physically examine products in retail outlets, warehouses, and manufacturing facilities. Violations can result in penalties, seizure of goods, or prosecution.

Despite the regulatory framework, there is no widely adopted digital tool that:

1. Guides inspectors through a complete package inspection.
2. Extracts declarations from package images using OCR.
3. Evaluates extracted declarations against structured legal rules.
4. Preserves evidence with coordinates and image references.
5. Produces auditable inspection reports.

---

## 4. Product Vision

DRISHTI is a **physical packaged-commodity inspection platform** that:

1. Converts package images into structured regulatory evidence.
2. Evaluates that evidence against applicable Legal Metrology requirements.
3. Produces deterministic PASS / FAIL / REVIEW outcomes with full evidence traceability.

DRISHTI is **not** a generic OCR scanner. It is **not** an AI that declares compliance. It is a structured inspection tool with a deterministic legal rule engine at its core.

### Core Pipeline

```
PACKAGED COMMODITY IMAGE
       ↓
OpenCV preprocessing (where applicable)
       ↓
PaddleOCR
       ↓
RAW OCR EVIDENCE
(text, confidence, polygon, image ID, panel, version, timestamp)
       ↓
TEXT NORMALIZATION
       ↓
DETERMINISTIC DECLARATION CLASSIFICATION
(regex, pattern matching, structured parsers)
       ↓
STRUCTURED EVIDENCE
       ↓
PRODUCT / PACKAGE CONTEXT
       ↓
INSPECTION COMPLETENESS CHECK
       ↓
VERSION-AWARE RULE SELECTION
       ↓
DETERMINISTIC LEGAL RULE ENGINE
       ↓
PASS / FAIL / REVIEW
```

If required inspection surfaces are incomplete → `INCOMPLETE_INSPECTION`

If a system component fails → explicit SYSTEM ERROR CODE

**NO FALLBACK. ONE PIPELINE. ONE SOURCE OF TRUTH.**

---

## 5. Goals

| # | Goal | Measure |
|---|------|---------|
| G1 | Structured extraction of mandatory declarations from package images | Declaration extraction precision and recall on validation corpus |
| G2 | Deterministic legal compliance evaluation | Rule decision accuracy on labelled test cases |
| G3 | Complete package inspection model | Correct INCOMPLETE INSPECTION detection when panels are missing |
| G4 | Evidence traceability | Every finding links to source image, coordinates, and extracted text |
| G5 | Auditable inspection history | Full inspection lifecycle persisted with evidence integrity |
| G6 | Professional reporting | PDF/DOCX reports with findings, evidence, and legal citations |
| G7 | Regulatory dashboards | Enforcement analytics for supervisors |

---

## 6. What DRISHTI Is NOT

- **Not an AI compliance oracle.** AI does not make final legal decisions.
- **Not a generic OCR tool.** OCR is one step in a structured inspection pipeline.
- **Not a label designer.** DRISHTI inspects existing packages; it does not create labels.
- **Not a consumer app.** Primary users are Legal Metrology inspectors and enforcement officers.
- **Not a barcode scanner.** DRISHTI reads label text, not product barcodes (unless explicitly required later).
- **Not a marketplace compliance plugin.** E-commerce integration is deferred scope.
- **Not a blockchain system.** Evidence integrity uses SHA-256 hashing, not distributed ledgers.

---

## 7. Target Users

### Primary

| User | Description |
|------|-------------|
| **Legal Metrology Inspector / Enforcement Officer** | Conducts field inspections of packaged commodities. Creates inspections, captures images, reviews findings, generates reports. |

### Secondary

| User | Description |
|------|-------------|
| **Supervising Officer** | Reviews completed inspections. Approves or reopens findings. Views enforcement analytics. |
| **System Administrator** | Manages users, system configuration, and deployment. |
| **Legal / Rule Administrator** | Maintains structured regulatory rules, rule versions, amendments, and activation status. |
| **Manufacturer / Packer / Importer** | Uses pre-production label verification to check compliance before market release. |

### Deferred

| User | Description |
|------|-------------|
| **Retail / E-commerce Compliance Team** | Compliance verification for online product listings. |

---

## 8. User Roles and Permissions

### INSPECTOR

- Create new inspections
- Capture product images (guided multi-panel)
- Review extracted declarations and evidence
- View compliance findings
- Generate inspection reports
- View own inspection history

### SUPERVISOR

- All INSPECTOR permissions
- Review inspections created by inspectors
- Approve or reopen findings
- View enforcement analytics and dashboards
- View all inspections within jurisdiction

### ADMIN

- Manage user accounts (create, activate, deactivate)
- Manage system configuration
- View system health and audit logs

### RULE_ADMIN

- Create and maintain structured regulatory rules
- Manage rule versions and effective dates
- Record amendments and source references
- Activate or deactivate applicable rule versions

---

## 9. Pain Points Addressed

| # | Pain Point | DRISHTI Solution |
|---|-----------|------------------|
| 1 | Manual reading of small, dense label text | OCR extraction with structured evidence |
| 2 | Missed declarations on uninspected surfaces | Guided multi-panel inspection with INCOMPLETE INSPECTION state |
| 3 | Inconsistent rule application across inspectors | One deterministic rule engine with versioned rules |
| 4 | No preserved evidence | Every finding linked to source image, coordinates, confidence |
| 5 | Outdated rule knowledge | Version-aware rules with effective dates and amendment tracking |
| 6 | Time-consuming report writing | Automated PDF/DOCX report generation |
| 7 | No enforcement analytics | Dashboards with violation trends, compliance rates, inspection volumes |

---

## 10. Core Use Cases

### UC-01: New Inspection

Inspector creates a new inspection, enters product details, and begins guided package capture.

### UC-02: Guided Package Capture

System determines required package panels based on product type. Inspector captures images panel by panel. System validates image quality before proceeding.

### UC-03: Declaration Extraction

System processes captured images through PaddleOCR and OpenCV. Extracts text with confidence scores and bounding coordinates. Classifies extracted text into declaration categories.

### UC-04: Compliance Evaluation

System selects applicable legal rules based on product classification, package type, and inspection date. Deterministic rule engine evaluates structured evidence against each applicable rule. Returns PASS / FAIL / REVIEW per rule.

### UC-05: Evidence Review

Inspector reviews findings with linked evidence. Can click any finding to see the source image with highlighted evidence region.

### UC-06: Report Generation

Inspector generates a PDF or DOCX report containing findings, evidence references, legal citations, and inspection metadata.

### UC-07: Inspection History

Inspector and supervisor can view past inspections, filter by status, product, date, and violation type.

### UC-08: Supervisor Review

Supervisor reviews completed inspections, approves or reopens findings, and views enforcement analytics.

### UC-09: Rule Administration

Rule administrator creates, versions, and manages structured legal rules with effective dates and source references.

---

## 11. Core Workflow

```
Login
  ↓
Dashboard (inspections overview, key metrics)
  ↓
New Inspection
  ↓
Product Details (name, category, package type)
  ↓
Determine Required Package Panels
  ↓
Guided Package Capture (panel by panel)
  ↓
Image Quality Validation (per panel)
  ↓
OCR / CV Processing
  ↓
Declaration Extraction → Structured Evidence
  ↓
Applicable Rule Selection (version-aware)
  ↓
Deterministic Rule Evaluation
  ↓
Result: PASS / FAIL / REVIEW / INCOMPLETE INSPECTION
  ↓
Evidence & Violation View
  ↓
Save Inspection
  ↓
Generate Report (PDF / DOCX)
  ↓
Inspection History / Analytics
```

---

## 12. MVP Definition

The Minimum Viable Product demonstrates the complete vertical pipeline:

**One image → OCR extraction → structured evidence → deterministic rule evaluation → result with evidence.**

### MVP Includes

1. Single-image upload (front panel).
2. Image quality validation (basic: blur, file type, dimensions).
3. PaddleOCR text extraction with confidence and coordinates.
4. Declaration classification for initial scope (see §14).
5. Deterministic rule evaluation for 3–5 core rules.
6. Result display: PASS / FAIL / REVIEW with linked evidence.
7. Basic inspection persistence.
8. Simple authentication (JWT).

### MVP Excludes

- Multi-panel guided inspection
- Calibrated physical measurement
- PDF/DOCX report generation
- Dashboards and analytics
- Supervisor workflow
- Rule administration UI
- RAG assistant
- E-commerce / manufacturer modes

---

## 13. Functional Requirements

### Image Input

| ID | Requirement |
|----|------------|
| FR-IMG-01 | Accept image uploads (JPEG, PNG) with file validation |
| FR-IMG-02 | Validate MIME type server-side |
| FR-IMG-03 | Enforce maximum file size |
| FR-IMG-04 | Detect blur, glare, poor lighting |
| FR-IMG-05 | Detect irrelevant objects (not a packaged commodity) |
| FR-IMG-06 | Detect empty, corrupt, or unreadable images |
| FR-IMG-07 | Return actionable rejection reasons |

### OCR and Extraction

| ID | Requirement |
|----|------------|
| FR-OCR-01 | Extract text using PaddleOCR only |
| FR-OCR-02 | Return detected text, confidence, and bounding polygon |
| FR-OCR-03 | Associate extracted text with source image and panel |
| FR-OCR-04 | Handle rotated, curved, and perspective-distorted text |
| FR-OCR-05 | Return OCR_PROCESSING_FAILED on OCR failure (no fallback) |

### Declaration Classification

| ID | Requirement |
|----|------------|
| FR-DEC-01 | Classify extracted text into declaration categories |
| FR-DEC-02 | Normalize declarations into structured fields |
| FR-DEC-03 | Preserve raw extracted text alongside normalized values |
| FR-DEC-04 | Flag low-confidence or ambiguous classifications for REVIEW |

### Rule Engine

| ID | Requirement |
|----|------------|
| FR-RUL-01 | Maintain structured regulatory rules with legal citations |
| FR-RUL-02 | Support rule versioning with effective dates |
| FR-RUL-03 | Select applicable rules based on product category, package type, and inspection date |
| FR-RUL-04 | Evaluate rules deterministically |
| FR-RUL-05 | Return PASS, FAIL, REVIEW, or INCOMPLETE_INSPECTION per rule |
| FR-RUL-06 | Every finding references supporting evidence |
| FR-RUL-07 | Return `RULE_EVALUATION_FAILED` on engine failure (no fallback) |
| FR-RUL-08 | Return `RULE_CONFIGURATION_ERROR` when an applicable rule is malformed or invalid — do not silently skip; do not produce COMPLIANT result |

### Inspection Management

| ID | Requirement |
|----|------------|
| FR-INS-01 | Create, save, and retrieve inspections |
| FR-INS-02 | Track inspection status (DRAFT, PROCESSING, COMPLETED, REVIEW_PENDING) |
| FR-INS-03 | Associate inspections with inspector, product, and date |
| FR-INS-04 | Support guided multi-panel capture (post-MVP) |
| FR-INS-05 | Detect INCOMPLETE INSPECTION when required panels are missing |

### Reporting

| ID | Requirement |
|----|------------|
| FR-RPT-01 | Generate PDF inspection reports |
| FR-RPT-02 | Generate DOCX inspection reports |
| FR-RPT-03 | Include findings, evidence references, legal citations |
| FR-RPT-04 | Return REPORT_GENERATION_FAILED on failure (no fallback) |

### User Management

| ID | Requirement |
|----|------------|
| FR-USR-01 | JWT-based authentication |
| FR-USR-02 | Role-based access control (INSPECTOR, SUPERVISOR, ADMIN, RULE_ADMIN) |
| FR-USR-03 | Argon2id password hashing |
| FR-USR-04 | Server-side authorization on all endpoints |

---

## 14. Non-Functional Requirements

| ID | Requirement | Target |
|----|------------|--------|
| NFR-01 | OCR processing for a single image | < 10 seconds |
| NFR-02 | Rule evaluation for a single inspection | < 2 seconds |
| NFR-03 | API response for non-processing endpoints | < 500ms |
| NFR-04 | Concurrent inspections supported | ≥ 10 simultaneous |
| NFR-05 | Evidence integrity | SHA-256 hash per evidence image |
| NFR-06 | Accessibility | WCAG 2.1 AA for primary workflows |
| NFR-07 | Browser support | Chrome, Edge, Firefox (latest 2 versions) |
| NFR-08 | Primary target devices | Desktop, tablet |
| NFR-09 | Scanning workflow | Mobile-compatible |

---

## 15. Initial Declaration Scope

The following declarations are in-scope for initial implementation:

| # | Declaration | Field Key |
|---|-------------|-----------|
| 1 | Manufacturer / Packer / Importer name | `manufacturer_name` |
| 2 | Manufacturer / Packer / Importer address | `manufacturer_address` |
| 3 | Common or generic product name | `product_name` |
| 4 | Net quantity | `net_quantity` |
| 5 | Maximum Retail Price (MRP) | `mrp` |
| 6 | Date of manufacture / packing / import | `date_of_manufacture` |
| 7 | Consumer care details | `consumer_care` |
| 8 | Country of origin (where applicable) | `country_of_origin` |

> [!IMPORTANT]
> Additional declarations will only be added when confirmed by authoritative legal sources. No declaration requirement will be invented.

---

## 16. Input Handling

### Valid Inputs

- JPEG or PNG image of a packaged commodity surface
- Image containing readable label/declaration text

### Invalid Inputs — Explicit Handling Required

| Input | Response |
|-------|----------|
| Irrelevant object (person, chair, laptop, etc.) | `INVALID_PACKAGE_IMAGE` |
| Empty image | `INVALID_PACKAGE_IMAGE` |
| No packaged commodity detected | `INVALID_PACKAGE_IMAGE` |
| Invalid file type | `INVALID_FILE_TYPE` |
| Blurry image | `IMAGE_RETAKE_REQUIRED` — Blur detected |
| Excessive glare | `IMAGE_RETAKE_REQUIRED` — Glare detected |
| Poor lighting | `IMAGE_RETAKE_REQUIRED` — Poor lighting |
| Severe perspective distortion | `IMAGE_RETAKE_REQUIRED` — Perspective distortion |
| Cropped label | `IMAGE_RETAKE_REQUIRED` — Incomplete label |
| Rotated image (correctable) | Auto-correct and process |
| Unreadable text | `LOW_OCR_CONFIDENCE` |
| Unsupported product category | `UNSUPPORTED_PRODUCT` |
| Duplicate panel | `DUPLICATE_PANEL` |
| Low OCR confidence | `LOW_OCR_CONFIDENCE` — flag for REVIEW |
| Missing calibration marker | `PHYSICAL_MEASUREMENT_UNAVAILABLE` |

---

## 17. Outputs

### Per-Rule Result

```
PASS | FAIL | REVIEW | INCOMPLETE INSPECTION
```

### Per Inspection

- Overall compliance status
- List of findings with:
  - Rule evaluated
  - Legal citation
  - Result (PASS / FAIL / REVIEW)
  - Evidence references (image, coordinates, extracted text, confidence)
  - Explanation
- Evidence gallery with bounding-box overlays
- Inspector notes (if any)

### Reports

- PDF report
- DOCX report (editable)

---

## 18. PASS / FAIL / REVIEW / INCOMPLETE INSPECTION Model

### PASS

The requirement is satisfied with sufficient evidence. Extracted declaration matches the legal rule with acceptable confidence.

### FAIL

A deterministic, verifiable rule violation exists. The evidence clearly shows non-compliance (e.g., MRP is missing entirely from all inspected surfaces, net quantity format violates rules).

### REVIEW REQUIRED

Evidence exists but is insufficient or ambiguous for an automated determination. Examples:
- OCR extracted text with low confidence
- Declaration found but value is ambiguous
- Classification uncertain

> [!IMPORTANT]
> REVIEW is a legitimate evidence state, not a fallback or error catch-all.

### INCOMPLETE INSPECTION

Required package surfaces or information have not yet been captured. The system cannot conclude a declaration is missing if relevant panels have not been inspected.

**Example:**
- Consumer care information not found on the FRONT panel.
- BACK panel has not been captured.
- Result: `INCOMPLETE INSPECTION` — not `FAIL`.

### SYSTEM ERROR

A required system component failed (OCR crash, database unavailable, rule engine failure). Distinct from evidence-based results.

---

## 19. Complete Package Inspection Model

DRISHTI models the physical package, not just "a set of images."

### Package Surfaces

| Panel | Description |
|-------|-------------|
| FRONT | Primary display panel |
| BACK | Rear panel |
| LEFT | Left side panel |
| RIGHT | Right side panel |
| TOP | Top panel |
| BOTTOM | Bottom panel |

### Panel States

| State | Description |
|-------|-------------|
| `NOT_REQUIRED` | Panel not needed for this product type |
| `REQUIRED` | Panel needed but not yet captured |
| `CAPTURED` | Image captured and accepted |
| `RETAKE_REQUIRED` | Image quality insufficient |
| `PROCESSED` | OCR and extraction complete |

### Inspection Completeness

The system determines required panels based on product type and category. An inspection is only complete when all required panels have been captured and processed.

> [!IMPORTANT]
> If the product/package type cannot be reliably determined, the system must return `PACKAGE_TYPE_REVIEW_REQUIRED`. The system must NOT invent or assume required panel requirements for an unknown package type. Required panel logic may only proceed after the product/package type is confirmed.

---

## 20. Differentiators (vs. Prior Art / MetaMark)

| # | Differentiator |
|---|---------------|
| 1 | **Guided complete-package inspection** — physical package model, not just image upload |
| 2 | **Structured evidence with coordinates** — every finding linked to image region |
| 3 | **Calibrated visual metrology** — ArUco-based physical measurement, not pixel guessing |
| 4 | **Version-aware deterministic legal rules** — not hard-coded conditions scattered in code |
| 5 | **PASS / FAIL / REVIEW model** — not a compliance "score" |
| 6 | **Inspector/supervisor workflow** — role-based enforcement lifecycle |
| 7 | **Evidence integrity** — SHA-256 hashing, inspector attribution, processing version tracking |
| 8 | **Labelled test corpus** — measured metrics, not fabricated accuracy claims |
| 9 | **Official-style inspection reports** — PDF/DOCX with legal citations |
| 10 | **Enforcement intelligence** — regulatory dashboards with real data |

---

## 21. Excluded Scope

The following are explicitly excluded from the current project scope:

- Barcode/QR code scanning (unless explicitly added later)
- E-commerce product listing compliance
- Real-time video stream processing
- Multi-language label OCR beyond English and Hindi
- Blockchain-based evidence chain
- Mobile native application (responsive web is sufficient)
- Integration with government databases (unless explicitly required)
- Automated penalty calculation
- Product recall management
- Supply chain tracking

---

## 22. Known Limitations

- OCR accuracy depends on image quality, label condition, and text complexity.
- Curved, metallic, or translucent packaging surfaces may reduce extraction accuracy.
- Physical measurement requires a calibration reference marker in the image.
- Legal rules must be manually structured and verified against authoritative sources.
- The system cannot verify the truthfulness of declarations (e.g., whether the stated manufacturer actually produced the product).
- AI-assisted features, when introduced in a later phase, may require internet connectivity. However, AI is NOT part of the mandatory inspection pipeline. The core compliance pipeline operates fully without AI.

---

## 23. Success Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Declaration extraction precision | Correct declarations extracted / total declarations extracted | ≥ 85% on validation corpus |
| Declaration extraction recall | Correct declarations extracted / total declarations present | ≥ 80% on validation corpus |
| Rule decision accuracy | Correct PASS/FAIL/REVIEW decisions / total rule evaluations | ≥ 90% on labelled test cases |
| False violation rate | Incorrect FAIL results / total FAIL results | ≤ 5% |
| REVIEW rate | REVIEW results / total rule evaluations | Tracked (lower is better, but accuracy matters more) |
| Invalid image rejection accuracy | Correctly rejected invalid images / total invalid images | ≥ 95% |
| Average inspection duration | Time from inspection creation to completion | Tracked (baseline established) |

> [!CAUTION]
> All metrics must be measured on real validation data. Fabricated metrics are prohibited.

---

## 24. Validation Metrics

The validation corpus should include:

- Real packaged-product photographs
- Controlled modified labels
- Intentionally non-compliant examples

Test case categories:
- Valid MRP / Missing MRP / Malformed MRP
- Missing consumer care details
- Invalid net quantity format
- Missing manufacturer information
- Blur / Glare / Low contrast
- Rotated / Curved packaging
- Cropped images / Incomplete panel scans
- Irrelevant objects
- Missing calibration markers
- Duplicate images
- Ambiguous declarations

---

## 25. Demo Workflow

For demonstration purposes, the following workflow should be presentable:

1. Inspector logs in.
2. Inspector creates a new inspection for a packaged product.
3. Inspector captures/uploads front panel image.
4. System validates image quality.
5. System extracts text via PaddleOCR.
6. System classifies declarations (MRP, manufacturer, net quantity, etc.).
7. System evaluates applicable rules.
8. System displays results: PASS / FAIL / REVIEW per declaration.
9. Inspector clicks a finding to see highlighted evidence on the original image.
10. Inspector generates a PDF report.

---

## 26. Future Scope

The following may be considered for future development:

- Full multi-panel guided inspection with 3D package visualization
- Calibrated physical font-size measurement using ArUco markers
- Legal Metrology RAG assistant for regulatory queries
- Manufacturer pre-production label verification mode
- E-commerce product listing compliance checking
- Multi-language OCR (regional Indian languages)
- Offline inspection capability with sync
- Integration with Legal Metrology department systems
- Mobile native application
- Batch inspection for warehouse audits
