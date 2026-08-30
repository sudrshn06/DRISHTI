# DRISHTI — SIH26034

**Legal Metrology Packaged-Commodity Inspection and Regulatory Intelligence Platform**

---

## What is DRISHTI?

DRISHTI converts package images into structured regulatory evidence and evaluates that evidence against applicable Legal Metrology (Packaged Commodities) Rules, 2011 requirements using a deterministic rule engine.

It is built for Legal Metrology inspectors and enforcement officers to conduct structured, auditable, evidence-based packaged-commodity inspections.

**SIH Reference:** SIH26034

---

## Current Development Phase

**Phase 0 — Foundation**

Infrastructure and scaffolding only. No compliance features are implemented yet.

---

## Architecture (Approved)

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite + Tailwind CSS |
| HTTP Client | Axios (sole client) |
| State | React Context + useReducer |
| Animations | Anime.js |
| Backend | Python + FastAPI + Pydantic v2 |
| Database | PostgreSQL + SQLAlchemy 2.x + Alembic |
| OCR | PaddleOCR ONLY — not yet implemented |
| Computer Vision | OpenCV — not yet implemented |
| Legal Engine | Custom deterministic Python — not yet implemented |
| Deployment | Docker + Docker Compose |

**No fallback mechanisms exist or will be added.**

---

## Implementation Status

| Feature | Status |
|---------|--------|
| Project structure | ✅ Phase 0 |
| Health endpoint (`GET /api/health`) | ✅ Phase 0 |
| PostgreSQL connection | ✅ Phase 0 |
| Alembic initialization | ✅ Phase 0 |
| Docker Compose (frontend + backend + postgres) | ✅ Phase 0 |
| Frontend app shell | ✅ Phase 0 |
| Authentication / RBAC | 🔜 Phase 8 |
| PaddleOCR integration | 🔜 Phase 1 |
| Declaration classification | 🔜 Phase 2 |
| Legal rule engine | 🔜 Phase 3 |
| Evidence viewer | 🔜 Phase 4 |
| Multi-panel inspection | 🔜 Phase 5 |
| Image quality validation | 🔜 Phase 6 |
| Calibrated measurement | 🔜 Phase 6 |
| PDF/DOCX reports | 🔜 Phase 9 |
| Dashboard / analytics | 🔜 Phase 10 |
| RAG assistant | 🔜 Phase 11 (optional) |

---

## Prerequisites

- **Node.js** 18+ (`node --version`)
- **npm** 9+ (`npm --version`)
- **Python** 3.11+ (`python --version`)
- **pip** (`pip --version`)
- **Docker** (`docker --version`)
- **Docker Compose** (`docker compose version`)

---

## Running the Project

### Option 1 — Docker Compose (recommended)

Copy `.env.example` to `.env` and set a real `POSTGRES_PASSWORD`:

```bash
cp .env.example .env
docker compose up --build
```

Services:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Backend health: http://localhost:8000/api/health
- PostgreSQL: localhost:5432

### Option 2 — Local development

**Backend:**

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp ../.env.example .env   # edit DATABASE_URL to point to local postgres
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

---

## Ports

| Service | Port |
|---------|------|
| Frontend | 3000 |
| Backend API | 8000 |
| PostgreSQL | 5432 |

---

## Project Structure

```
DRISHTI/
├── docs/               # Planning documents (approved, do not modify without review)
│   ├── 1-product.md
│   ├── 2-architecture.md
│   ├── 3-rules.md      ← permanent engineering constraints
│   ├── 4-phases.md
│   └── 5-design.md
├── frontend/           # React + Vite application
├── backend/            # FastAPI application
├── tests/              # Cross-cutting test utilities
├── memory.md           # Live engineering state
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Engineering Rules

All development follows `/docs/3-rules.md` without exception. Key principles:

- **One implementation per capability** — no fallback engines or duplicate providers
- **Explicit failure** — no silent substitution
- **Deterministic legal evaluation** — rule engine is the sole compliance authority
- **Evidence-first** — all findings trace to source images and coordinates

---

## Legal Notice

DRISHTI evaluates packaged commodity compliance against Legal Metrology (Packaged Commodities) Rules, 2011. All regulatory rules must be verified against authoritative sources (Department of Consumer Affairs, official Gazette notifications). No legal requirement is invented.
