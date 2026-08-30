# DRISHTI — Engineering Rules

> This document contains permanent engineering rules for the DRISHTI project.
> All contributors — human and AI — must follow these rules without exception.

---

## ⛔ NO FALLBACK MECHANISMS

**THIS IS THE MOST IMPORTANT RULE IN THIS PROJECT.**

DRISHTI must use **ONE explicitly selected implementation** for every core capability. There must be:

- **NO** fallback OCR engine
- **NO** Tesseract backup
- **NO** second OCR provider
- **NO** fallback AI provider
- **NO** automatic AI model switching
- **NO** alternate hidden processing pipeline
- **NO** silent degraded mode
- **NO** fabricated default result
- **NO** guessed legal result
- **NO** automatic substitution when a component fails

### Examples

| Scenario | Correct Response | Incorrect Response |
|----------|-----|------|
| PaddleOCR fails | `OCR_PROCESSING_FAILED` → preserve state → Retry | Silently use Tesseract |
| AI service fails | `AI_SERVICE_UNAVAILABLE` → preserve state → Retry | Switch to another AI provider |
| Rule engine fails | `RULE_EVALUATION_FAILED` → preserve state | Return partial results |
| Database fails | `DATABASE_UNAVAILABLE` → preserve state | Cache and proceed |
| Calibration unavailable | `PHYSICAL_MEASUREMENT_UNAVAILABLE` | Estimate from pixels |

**ONE PIPELINE. ONE SOURCE OF TRUTH. EXPLICIT FAILURE. NO HIDDEN FALLBACKS.**

> [!CAUTION]
> A component failure must remain visible. Do not silently switch to another implementation.

---

## 1. Think Before Coding

- Do not assume requirements. Surface meaningful assumptions.
- Identify tradeoffs before choosing a solution.
- Prefer simpler solutions over clever ones.
- Do not silently select between materially different interpretations.
- If a requirement is ambiguous, ask — do not guess.

---

## 2. Simplicity First

- Implement the **minimum** needed for the current requirement.
- No speculative abstractions.
- No unnecessary configurability.
- No future infrastructure unless it is required **now**.
- Avoid overengineering.
- If you are building something "in case we need it later" — stop.

---

## 3. Surgical Changes

When editing existing code:

- Modify **only** the files required for the current task.
- Do not randomly refactor unrelated code.
- Do not change unrelated formatting.
- Preserve working interfaces.
- Clean only code made obsolete by the current change.

**Every changed line should be traceable to the requested task.**

---

## 4. Goal-Driven Execution

Every development task must define:

| Section | Content |
|---------|---------|
| **GOAL** | What this task achieves |
| **IMPLEMENTATION** | What will be built/changed |
| **ACCEPTANCE CRITERIA** | How to verify success |
| **TESTS** | What tests will be written |
| **VERIFICATION** | How to run verification |

### Example

```
GOAL:
Validate MRP declaration presence and format.

IMPLEMENTATION:
Add MRP presence and format validators to rule engine.

ACCEPTANCE CRITERIA:
- Valid MRP → PASS
- Missing MRP (all panels inspected) → FAIL
- Missing MRP (not all panels inspected) → INCOMPLETE INSPECTION
- Malformed MRP → FAIL
- Ambiguous MRP (low OCR confidence) → REVIEW

TESTS:
test_mrp_valid, test_mrp_missing, test_mrp_malformed,
test_mrp_incomplete_panels, test_mrp_low_confidence

VERIFICATION:
pytest tests/backend/test_rule_engine.py -v
```

---

## 5. Legal Source Policy

### Authoritative Sources

Regulatory ground truth must come from:

- Department of Consumer Affairs
- Legal Metrology Act, 2009
- Legal Metrology (Packaged Commodities) Rules, 2011
- Official amendments
- Official Gazette notifications

### Prohibitions

- **Never invent** legal citations.
- **Never invent** regulatory requirements.
- **Never rely on** blog posts as primary legal authority.
- **Never hard-code** legal conditions in controllers or frontend components.
- Every implemented legal control must be **traceable** to an authoritative source.

---

## 6. Deterministic Decision Policy

The deterministic rule engine is the **sole authority** for legal compliance decisions.

- All legal evaluation goes through **one rule engine module**.
- Same evidence + same rules = same result. Always.
- Every finding must include an explanation.
- Every finding must reference supporting evidence.
- Legal rules must not be scattered across controllers, services, or frontend components.

---

## 7. AI Boundaries

> [!IMPORTANT]
> AI is NOT part of the mandatory DRISHTI core pipeline. The pipeline from Image → PaddleOCR → Deterministic Classification → Evidence → Rule Engine → PASS/FAIL/REVIEW operates entirely without AI. AI may only be introduced in a later, explicitly approved phase after ONE provider and ONE model have been deliberately selected.

### AI MAY (only after explicit introduction in an approved later phase)

- Explain already-determined legal findings
- Power a Legal Metrology RAG assistant using official documents
- Assist evidence interpretation for explicitly approved semantic tasks

### AI MUST NOT

- Make final legal PASS/FAIL decisions
- Invent legal requirements or citations
- Invent or fabricate evidence
- Fabricate confidence values
- Fabricate missing declarations
- Override deterministic rule-engine results
- Infer text that is not supported by evidence
- Decide compliance in place of the deterministic rule engine

### AI Failure (when AI has been introduced)

- `AI_SERVICE_UNAVAILABLE` → preserve state → log error → display Retry
- No fallback AI provider
- No fallback AI model
- No silent substitution through another model or provider
- No silent retries through another implementation

---

## 8. OCR Policy

- **PaddleOCR is the sole OCR engine.**
- No Tesseract. No Google Vision. No Amazon Textract. No second OCR provider.
- OCR failure → `OCR_PROCESSING_FAILED` → preserve state → Retry.
- No fallback OCR of any kind.

---

## 9. Approved Technology Stack

| Layer | Approved Technology |
|-------|-------------------|
| Frontend | React, Vite, Tailwind CSS, Lucide React, Recharts, Anime.js, selected React Bits |
| HTTP Client | Axios (sole HTTP client — no Fetch API, no alternative) |
| State Management | React Context + useReducer (sole state library — no Zustand, no Redux) |
| Backend | Python, FastAPI, Pydantic v2 |
| Database | PostgreSQL, SQLAlchemy 2.0, Alembic |
| OCR | PaddleOCR ONLY — no Tesseract, no EasyOCR, no cloud OCR backup |
| Computer Vision | OpenCV |
| AI | ONE selected provider, ONE selected model (when explicitly introduced in a later phase) |
| Rule Engine | Custom deterministic Python |
| PDF Reports | ReportLab |
| DOCX Reports | python-docx |
| Testing | pytest |
| Deployment | Docker, Docker Compose |
| Storage (dev) | Local filesystem (sole active storage during development) |
| Storage (prod migration) | MinIO / S3-compatible (deployment-phase migration only, not runtime fallback) |

---

## 10. Prohibited Technologies

Do NOT add unless specifically required and approved:

- Redis
- Celery
- Kafka
- Kubernetes
- Blockchain
- Multiple OCR engines
- Multiple AI providers
- Tesseract
- EasyOCR
- Zustand
- Redux
- Unnecessary microservices
- GraphQL (use REST)
- MongoDB (use PostgreSQL)
- Firebase
- Second OCR implementation
- Duplicate backend (no "backend_new", "backend_v2")

---

## 11. Dependency Policy

- Every dependency must have a clear justification.
- Prefer well-maintained, widely-used libraries.
- Do not add dependencies for trivial functionality that can be implemented in a few lines.
- Document every added dependency in `requirements.txt` (backend) or `package.json` (frontend).
- Pin dependency versions.

---

## 12. Anime.js Policy

Anime.js is the primary engine for custom workflow animations.

### Appropriate Uses

- Guided package-scan progression
- Panel completion transitions
- OCR evidence-box reveal
- Compliance processing state indicators
- Evidence sequence visualization
- Violation focus animations
- PASS / FAIL / REVIEW result transitions
- Report generation state
- Dashboard value animations (CountUp-style)
- SVG package visualizations
- Inspection pipeline transitions

### Prohibitions

> [!CAUTION]
> **Animations must reflect real application/backend state. The frontend must never fabricate compliance results, confidence values, progress percentages, legal findings, inspection state, or evidence.**

- Never animate fake values.
- Never generate fake progress percentages.
- Never visually imply analysis completed before the backend confirms it.
- Never use animation to disguise loading or failure states.

---

## 13. React Bits Policy

React Bits may be used **selectively**. It is not mandatory to use every component.

### Potentially Useful

- CountUp — dashboard metrics
- Stepper — inspection workflow
- AnimatedList — evidence/findings lists
- FadeContent — content transitions
- AnimatedContent — panel transitions
- Carefully selected cards

### Avoid

- Threads
- DotGrid
- Shader backgrounds
- WebGL decoration
- TiltedCard everywhere
- GlareHover everywhere
- Excessive glowing effects
- Neon
- Particles
- Futuristic AI visuals

**DRISHTI should look like a serious modern regulatory inspection platform — not a gaming dashboard or AI demo website.**

---

## 14. API Change Policy

- All API endpoints must have Pydantic request/response schemas.
- API changes must be backward-compatible where possible.
- Breaking API changes must be documented and coordinated with frontend changes.
- Every endpoint must validate input server-side.
- Every endpoint must enforce RBAC server-side.

---

## 15. Database Migration Policy

- All schema changes go through Alembic migrations.
- Never modify the database schema directly.
- Every migration must have a descriptive message.
- Migrations must be reversible (include downgrade).
- Test migrations on a fresh database before merging.

---

## 16. Security Policy

### Required

- JWT authentication on all protected endpoints
- RBAC enforced server-side
- Argon2id password hashing (via `argon2-cffi`)
- Server-side authorization — never trust frontend role claims
- Environment variables for all secrets
- File validation (MIME type, size, content)
- Request validation (Pydantic)
- Upload size controls
- Secure database handling (parameterized queries via ORM)

### Prohibited

- **Never** commit credentials or API keys
- **Never** hard-code secrets in source code
- **Never** store plaintext passwords
- **Never** use raw SHA-256 for password storage
- **Never** trust frontend-submitted role claims for authorization
- **Never** log sensitive data (passwords, tokens, API keys)

---

## 17. Error Policy

### Principles

- Never hide errors.
- Never catch exceptions and return fake success.
- Use explicit, named error states.
- All errors must be logged.
- All errors must be returned using meaningful API responses.
- All errors must be presented clearly in the frontend.
- Errors must be recoverable through explicit Retry where appropriate.

### Standard Error States

| Error State | Meaning |
|-------------|---------|
| `OCR_PROCESSING_FAILED` | PaddleOCR failed to process the image |
| `IMAGE_RETAKE_REQUIRED` | Image quality is insufficient |
| `INVALID_PACKAGE_IMAGE` | Image does not contain a packaged commodity |
| `AI_SERVICE_UNAVAILABLE` | AI provider is not reachable (when AI has been introduced) |
| `DATABASE_UNAVAILABLE` | Database connection failed |
| `RULE_EVALUATION_FAILED` | Rule engine encountered an error |
| `RULE_CONFIGURATION_ERROR` | An applicable rule is malformed, invalid, or cannot be executed — evaluation cannot produce a COMPLIANT result |
| `RULE_VERSION_UNAVAILABLE` | No applicable rule version found |
| `PHYSICAL_MEASUREMENT_UNAVAILABLE` | Calibration reference not available |
| `REPORT_GENERATION_FAILED` | Report generation failed |
| `INCOMPLETE_INSPECTION` | Required panels not yet captured |
| `PACKAGE_TYPE_REVIEW_REQUIRED` | Product/package type cannot be reliably determined — panel requirements cannot be assumed |
| `INVALID_FILE_TYPE` | Uploaded file is not a supported type |
| `DUPLICATE_PANEL` | Same panel already captured |
| `LOW_OCR_CONFIDENCE` | OCR text extraction confidence below threshold |
| `NO_USABLE_TEXT_DETECTED` | PaddleOCR processed the image successfully but detected no usable text |
| `UNSUPPORTED_PRODUCT` | Product category not supported |

### NO FALLBACK PROCESSING

When an error occurs:
1. Log the error with context.
2. Return the specific error state.
3. Preserve current inspection state.
4. Present Retry option where appropriate.
5. **Do not silently switch to another implementation.**

---

## 18. Secrets Policy

- All secrets and API keys must be stored as environment variables.
- Use `.env` files for local development only.
- `.env` must be in `.gitignore`.
- Provide `.env.example` with placeholder values.
- Never commit `.env` files.
- Never hard-code secrets in source code, configuration files, or documentation.

---

## 19. Evidence Policy

### Evidence Integrity

```
Original Image
    ↓
SHA-256 hash
    ↓
Timestamp
    ↓
Inspector ID
    ↓
Processing version
    ↓
Rule version (at evaluation time)
    ↓
Finding
```

- Every evidence record must be immutable after creation.
- Corrections create new evidence records linked to the original.
- Evidence must be traceable from finding → evidence → image.
- Original images must never be modified.
- Annotated/highlighted images are stored separately from originals.

### Evidence Display

The frontend must support:

```
Click finding → Open source image → Highlight evidence region (bounding box)
```

---

## 20. Testing Requirements

- All rule engine validators must have unit tests.
- All API endpoints must have integration tests.
- OCR pipeline must have tests against known images.
- Image validation must have tests for each rejection reason.
- Declaration classification must have tests for each category.
- Tests must use real or realistic test data — never fabricated metrics.
- Use pytest as the testing framework.

### Validation Corpus

DRISHTI must eventually maintain a labelled validation corpus with:

- Real packaged-product photographs
- Controlled modified labels
- Intentionally non-compliant examples
- Categorized test cases (valid, missing, malformed, blur, glare, rotated, etc.)

---

## 21. Naming Conventions

### Backend (Python)

| Element | Convention | Example |
|---------|-----------|---------|
| Files | snake_case | `ocr_engine.py` |
| Classes | PascalCase | `InspectionService` |
| Functions | snake_case | `evaluate_rule()` |
| Constants | UPPER_SNAKE_CASE | `MAX_UPLOAD_SIZE_MB` |
| Variables | snake_case | `inspection_id` |
| Pydantic Models | PascalCase | `CreateInspectionRequest` |
| SQLAlchemy Models | PascalCase (singular) | `Inspection` |
| Database Tables | snake_case (plural) | `inspections` |

### Frontend (JavaScript/React)

| Element | Convention | Example |
|---------|-----------|---------|
| Files (components) | PascalCase | `InspectionDetail.jsx` |
| Files (utilities) | camelCase | `apiClient.js` |
| Components | PascalCase | `EvidenceViewer` |
| Functions | camelCase | `fetchInspections()` |
| Constants | UPPER_SNAKE_CASE | `API_BASE_URL` |
| Variables | camelCase | `inspectionId` |
| CSS Classes | kebab-case (via Tailwind) | `bg-primary-500` |

### API

| Element | Convention | Example |
|---------|-----------|---------|
| Endpoints | kebab-case (nouns) | `/api/inspections/{id}/findings` |
| Query Parameters | snake_case | `?page_size=20&status=completed` |
| Request/Response Fields | snake_case | `inspection_id`, `created_at` |

---

## 22. Code Organization Rules

- **One responsibility per file** — a file should have one clear purpose.
- **No god files** — if a file exceeds ~400 lines, consider splitting by responsibility.
- **Imports at top** — organized by stdlib → third-party → local.
- **No circular imports** — use dependency injection or interface patterns if needed.
- **Type hints** — use Python type hints on all function signatures.
- **Docstrings** — all public functions and classes must have docstrings.

---

## 23. Git and Version Control

- Use descriptive commit messages.
- Commit atomic changes — one logical change per commit.
- Never commit generated files (node_modules, __pycache__, .env, build artifacts).
- Use `.gitignore` for all generated/sensitive files.
- Tag releases with semantic versioning when applicable.
