"""
DRISHTI Backend — FastAPI Application Entry Point

Evidence-first packaged commodity inspection and regulatory decision-support platform.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import health

app = FastAPI(
    title="DRISHTI API",
    description=(
        "Evidence-first packaged commodity inspection and regulatory "
        "decision-support platform."
    ),
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS — explicit development origins; keep credentialed requests origin-bound
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

@app.on_event("startup")
def startup_event():
    from app.db.session import SessionLocal
    from app.services.rag_ingestion_service import seed_approved_corpus
    db = SessionLocal()
    try:
        seed_approved_corpus(db)
    finally:
        db.close()

from fastapi.exceptions import RequestValidationError
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters."
            }
        },
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    headers = getattr(exc, "headers", None)
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=headers)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": str(exc.detail),
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail)
            }
        },
        headers=headers
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred."
            }
        },
    )

# --- Routers ---
app.include_router(health.router, prefix="/api", tags=["Health"])

# Import here to avoid circular imports if any, and router registration
from app.api.routes import ocr
app.include_router(ocr.router, prefix="/api/ocr", tags=["OCR"])

from app.api.routes import dashboard
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])

from app.api.routes import inspections
app.include_router(inspections.router, prefix="/api/inspections", tags=["Inspections"])

from app.api.routes import auth
app.include_router(auth.router, prefix="/api", tags=["Auth"])

from app.api.routes import rag
app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])
