from pydantic import BaseModel, Field
from typing import List, Literal

class ImageQualityAssessment(BaseModel):
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    blur_score: float = Field(..., description="Variance of Laplacian blur score")
    brightness: float = Field(..., description="Average pixel brightness (0-255)")
    glare_percentage: float = Field(..., description="Percentage of pixels considered glare/highlight")
    quality_status: Literal["ACCEPTABLE", "RETAKE_RECOMMENDED"] = Field(
        ..., description="Overall quality status based on heuristic thresholds"
    )
    reasons: List[str] = Field(default_factory=list, description="Reasons for RETAKE_RECOMMENDED status")
