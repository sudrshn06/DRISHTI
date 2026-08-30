"""Application boundary for optional contextual package-image observations."""

import uuid
from datetime import datetime, timezone

from app.schemas.gemini import (
    GeminiCaptureEvidenceReference,
    GeminiPackageAuditRecord,
)
from app.services.contextual_vision_provider import ContextualVisionProvider
from app.services.gemini_package_reader import default_gemini_reader


class ContextualVisionService:
    """Runs the configured provider and creates its isolated audit envelope."""

    def __init__(self, provider: ContextualVisionProvider) -> None:
        self.provider = provider

    async def analyze_capture(
        self,
        *,
        inspection_id: str,
        capture_id: str,
        view_id: str,
        image_sha256: str,
        image_bytes: bytes,
        media_type: str,
    ) -> GeminiPackageAuditRecord:
        analysis = await self.provider.analyze_package(
            image_bytes=image_bytes,
            media_type=media_type,
            view_id=view_id,
            capture_id=capture_id,
        )
        return GeminiPackageAuditRecord(
            audit_id=str(uuid.uuid4()),
            inspection_id=inspection_id,
            capture_evidence=[GeminiCaptureEvidenceReference(
                capture_id=capture_id,
                view_id=view_id,
                image_sha256=image_sha256,
            )],
            analysis=analysis,
            created_at=datetime.now(timezone.utc),
        )


default_contextual_vision_service = ContextualVisionService(default_gemini_reader)

