"""Provider contract for optional, non-authoritative package-image reading."""

from abc import ABC, abstractmethod
from typing import Optional

from app.schemas.gemini import GeminiPackageAnalysis


class ContextualVisionProvider(ABC):
    """Returns advisory observations without participating in legal evaluation."""

    @abstractmethod
    async def analyze_package(
        self,
        *,
        image_bytes: bytes,
        media_type: str,
        view_id: str,
        capture_id: Optional[str] = None,
    ) -> GeminiPackageAnalysis:
        """Analyze one capture and always degrade to a non-raising result."""

