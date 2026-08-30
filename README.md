# DRISHTI

**Packaged Commodity Inspection Portal — Every Label Counts**

DRISHTI is an evidence-first packaged-commodity inspection and decision-support system for Legal Metrology inspectors. It helps an authenticated officer capture package surfaces, assess image quality, extract visible declarations, reconcile machine observations, apply deterministic regulatory rules, review evidence, and finalize an evidence-backed report.

DRISHTI does not replace the inspecting officer. Gemini observations are contextual and advisory; they never make a legal decision. PaddleOCR is the sole OCR engine, deterministic Legal Metrology and scoped FSSAI label rules are authoritative, and officer approval is mandatory for finalization and any external portal handoff.

## Implemented inspection flow

```text
Capture
  → Image Quality Validation
  → PaddleOCR
  → Contextual Vision
  → Evidence Reconciliation
  → Applicability and Evidence Sufficiency
  → Deterministic Regulatory Rules
  → Officer Review
  → Finalized Evidence-backed Report
```

The default capture plan requires FRONT and BACK photographs and permits additional package surfaces. `FRONT` identifies the camera perspective; it is not automatically the statutory principal display panel. Completing the capture plan completes the requested workflow, but does not prove that every possible declaration-bearing surface was inspected. The active plan therefore keeps `absence_evaluation_eligible=False`.

## Current capabilities

- Guided desktop and mobile capture, including rear-camera input on supported phones.
- Image decoding, file validation, SHA-256 integrity metadata, and OpenCV quality checks.
- PaddleOCR text detection and recognition with confidence and source coordinates.
- Optional Gemini contextual vision using a configured model and a constrained schema.
- Hybrid evidence reconciliation with provider provenance, conflict review, and unsupported-inference blocking.
- Officer-confirmed package information and append-only declaration corrections.
- Deterministic Legal Metrology and scoped FSSAI label assessment.
- Explicit `PASS`, `FAIL`, `REVIEW_REQUIRED`, and `NOT_APPLICABLE` rule outcomes.
- PostgreSQL-backed inspections, users, report snapshots, and approved legal-help corpus.
- MinIO object storage with authenticated, inspection-authorized image retrieval.
- Inspection dashboard, history, rule library, evidence views, and responsive government-portal UI.
- Immutable finalized report snapshots with PDF, DOCX, and evidence-package output.
- Grounded legal-provision help over an approved local corpus.
- JWT authentication, Argon2id password hashing, Inspector/Admin roles, and inspection ownership controls.

## Decision and safety model

- A rule can pass only when its applicability, required evidence, and deterministic conditions are satisfied.
- Missing or contradictory evidence produces review, not an invented value or unsupported legal absence.
- A `FAIL` must be supported by rule-specific evidence and a legal reference.
- `NOT_APPLICABLE` means the rule does not apply to the confirmed context; it is not a pass.
- A finalized inspection is locked and auditable. Finalization is a workflow state, not a declaration that the product is compliant.
- Provider failures are explicit. DRISHTI does not silently switch OCR engines, Gemini providers, or models, and it does not fabricate output.

See [docs/6-absence-evaluation-safety.md](docs/6-absence-evaluation-safety.md) for the full absence-evaluation boundary.

## Technology

| Layer | Implemented technology |
|---|---|
| Frontend | React 19, Vite, Tailwind CSS, Axios, Recharts, Lucide icons |
| API | FastAPI, Pydantic, SQLAlchemy, Alembic |
| OCR and image processing | PaddleOCR, PaddlePaddle, OpenCV |
| Contextual vision | Google Gemini, configured as a non-authoritative provider |
| Decision support | Deterministic Python Legal Metrology and scoped FSSAI label rules |
| Data | PostgreSQL |
| Object storage | MinIO |
| Reports | ReportLab PDF, python-docx DOCX, evidence-package generation |
| Authentication | JWT and Argon2id |
| Local deployment | Docker Compose |

## Run with Docker Compose

Prerequisites:

- Docker Desktop with Docker Compose
- Available ports `3000`, `8000`, `5432`, `9000`, and `9001`
- Project environment configured locally; never commit secrets

From the repository root:

```bash
docker compose up -d --build
```

Services:

| Service | Address |
|---|---|
| Frontend | `http://localhost:3000` |
| Backend API | `http://localhost:8000` |
| API documentation | `http://localhost:8000/docs` |
| Health check | `http://localhost:8000/api/health` |
| PostgreSQL | `localhost:5432` |
| MinIO API | `localhost:9000` |
| MinIO console | `localhost:9001` |

The frontend derives its default API hostname from the page being viewed, which supports approved LAN development origins without hardcoding a single workstation address.

## Local development

Backend dependencies and database/environment settings are defined under `backend/`. Frontend commands are run from `frontend/`:

```bash
npm install
npm run dev
npm test
npm run lint
npm run build
```

Backend tests use `pytest`; database, object-storage, or live-provider tests require their corresponding services and credentials. Service failures must be reported separately from code regressions.

## Repository guide

```text
DRISHTI/
├── backend/
│   ├── alembic/                 # Database migrations
│   ├── app/
│   │   ├── api/routes/          # Auth, inspection, OCR, dashboard, RAG
│   │   ├── core/                # Configuration, security, middleware
│   │   ├── models/              # SQLAlchemy persistence models
│   │   ├── schemas/             # API and provider validation models
│   │   └── services/            # OCR, vision, reconciliation, rules, reports
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/          # Inspection, evidence, auth, shared UI
│   │   ├── pages/               # Dashboard, inspection, history, rules
│   │   └── services/            # API, device queue, session state
│   └── tests/
├── docs/                        # Product, architecture, rules, history, design, safety
└── docker-compose.yml
```

## Documentation

- [Product definition](docs/1-product.md)
- [System architecture](docs/2-architecture.md)
- [Engineering rules](docs/3-rules.md)
- [Historical development plan](docs/4-phases.md)
- [Current design system](docs/5-design.md)
- [Absence-evaluation safety boundary](docs/6-absence-evaluation-safety.md)

## Legal notice

DRISHTI provides evidence-backed decision support. Its output is not, by itself, a statutory finding, legal opinion, complaint, or enforcement action. An authorized officer must review the captured evidence, confirmed context, applicable provisions, and deterministic findings before finalization or external use.
