"""Strict advisory schemas for Gemini package understanding.

These models intentionally contain observations and context suggestions only.
Legal applicability and PASS/FAIL decisions are not representable here.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class StrictGeminiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeminiAnalysisStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    DISABLED = "DISABLED"
    TIMEOUT = "TIMEOUT"
    REFUSED = "REFUSED"
    QUOTA_UNAVAILABLE = "QUOTA_UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    FAILED = "FAILED"


class ProductOriginValue(str, Enum):
    DOMESTIC = "DOMESTIC"
    IMPORTED = "IMPORTED"
    UNKNOWN = "UNKNOWN"


class RegulatoryProductClassValue(str, Enum):
    FOOD = "FOOD"
    NON_FOOD = "NON_FOOD"
    UNKNOWN = "UNKNOWN"


class DateRegulatoryRegimeValue(str, Enum):
    GENERAL = "GENERAL"
    FOOD = "FOOD"
    CERTIFIED_SEED = "CERTIFIED_SEED"
    COSMETIC = "COSMETIC"
    UNKNOWN = "UNKNOWN"


class DatePackageExemptionValue(str, Enum):
    NONE = "NONE"
    BIDI_OR_INCENSE = "BIDI_OR_INCENSE"
    PSU_DOMESTIC_LPG_14_2_OR_5KG = "PSU_DOMESTIC_LPG_14_2_OR_5KG"
    UNKNOWN = "UNKNOWN"


class ElectronicContextValue(str, Enum):
    ELECTRONIC = "ELECTRONIC"
    NON_ELECTRONIC = "NON_ELECTRONIC"
    UNKNOWN = "UNKNOWN"


class PackageStructureValue(str, Enum):
    SINGLE = "SINGLE"
    COMBINATION = "COMBINATION"
    GROUP = "GROUP"
    MULTI_PIECE = "MULTI_PIECE"
    UNKNOWN = "UNKNOWN"


class AlcoholContextValue(str, Enum):
    ALCOHOLIC = "ALCOHOLIC"
    NON_ALCOHOLIC = "NON_ALCOHOLIC"
    UNKNOWN = "UNKNOWN"


class ContextSuggestionBase(StrictGeminiModel):
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str] = Field(..., min_length=1)
    uncertain: bool
    contradiction: bool


class ProductOriginSuggestion(ContextSuggestionBase):
    field: Literal["product_origin"]
    suggested_value: ProductOriginValue


class RegulatoryProductClassSuggestion(ContextSuggestionBase):
    field: Literal["regulatory_product_class"]
    suggested_value: RegulatoryProductClassValue


class DateRegulatoryRegimeSuggestion(ContextSuggestionBase):
    field: Literal["date_regulatory_regime"]
    suggested_value: DateRegulatoryRegimeValue


class DatePackageExemptionSuggestion(ContextSuggestionBase):
    field: Literal["date_package_exemption"]
    suggested_value: DatePackageExemptionValue


class ElectronicContextSuggestion(ContextSuggestionBase):
    field: Literal["is_electronic"]
    suggested_value: ElectronicContextValue


class PackageStructureSuggestion(ContextSuggestionBase):
    field: Literal["package_structure"]
    suggested_value: PackageStructureValue


class AlcoholContextSuggestion(ContextSuggestionBase):
    field: Literal["alcohol_context"]
    suggested_value: AlcoholContextValue


ContextSuggestion = Annotated[
    Union[
        ProductOriginSuggestion,
        RegulatoryProductClassSuggestion,
        DateRegulatoryRegimeSuggestion,
        DatePackageExemptionSuggestion,
        ElectronicContextSuggestion,
        PackageStructureSuggestion,
        AlcoholContextSuggestion,
    ],
    Field(discriminator="field"),
]


class ObservationBase(StrictGeminiModel):
    raw_text: str = Field(..., min_length=1)
    capture_id: Optional[str] = None
    view_id: Optional[str] = None
    normalized_bounding_box: Optional["NormalizedBoundingBox"] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    uncertain: bool
    contradiction: bool
    evidence_note: str = Field(..., min_length=1)
    review_state: Literal["OBSERVED", "REVIEW_REQUIRED"] = "OBSERVED"


class NormalizedBoundingBox(StrictGeminiModel):
    x_min: float = Field(..., ge=0.0, le=1.0)
    y_min: float = Field(..., ge=0.0, le=1.0)
    x_max: float = Field(..., ge=0.0, le=1.0)
    y_max: float = Field(..., ge=0.0, le=1.0)


class RawVisibleTextGroup(StrictGeminiModel):
    capture_id: Optional[str] = None
    view_id: Optional[str] = None
    visible_text: list[str] = Field(default_factory=list)


class MrpObservation(ObservationBase):
    amount: Optional[float] = Field(None, ge=0.0)
    currency: Optional[str] = None


class NetQuantityObservation(ObservationBase):
    value: Optional[float] = Field(None, ge=0.0)
    unit: Optional[str] = None


class BusinessObservation(ObservationBase):
    role: Literal["MANUFACTURER", "PACKER", "IMPORTER", "MARKETER"]
    name: Optional[str] = None
    address: Optional[str] = None
    pin_code: Optional[str] = None


class DateObservation(ObservationBase):
    date_type: Literal["MANUFACTURED", "PACKED", "IMPORTED", "USE_BY", "BEST_BEFORE", "EXPIRY", "UNKNOWN"]
    day: Optional[int] = Field(None, ge=1, le=31)
    month: Optional[int] = Field(None, ge=1, le=12)
    year: Optional[int] = Field(None, ge=1900, le=2200)
    duration: Optional[int] = Field(None, ge=0)
    duration_unit: Optional[str] = None


class CountryOfOriginObservation(ObservationBase):
    declaration_type: Literal["ORIGIN", "MANUFACTURE", "ASSEMBLY"]
    country_text: Optional[str] = None


class TextObservation(ObservationBase):
    value: Optional[str] = None


class ConsumerCareObservation(ObservationBase):
    email: Optional[str] = None
    phone: Optional[str] = None


class UnitSalePriceObservation(ObservationBase):
    amount: Optional[float] = Field(None, ge=0.0)
    currency: Optional[str] = None
    per_quantity: Optional[float] = Field(None, gt=0.0)
    per_unit: Optional[str] = None


class StructuredDeclarationObservations(StrictGeminiModel):
    mrp: Optional[MrpObservation] = None
    net_quantity: Optional[NetQuantityObservation] = None
    manufacturer_packer_importer: list[BusinessObservation] = Field(default_factory=list)
    dates: list[DateObservation] = Field(default_factory=list)
    country_of_origin: Optional[CountryOfOriginObservation] = None
    common_generic_name: Optional[TextObservation] = None
    brand_trade_name: Optional[TextObservation] = None
    consumer_care: Optional[ConsumerCareObservation] = None
    unit_sale_price: Optional[UnitSalePriceObservation] = None
    qr_common_name_instruction: Optional[TextObservation] = None
    fssai_licence: Optional[TextObservation] = None
    ingredients: Optional[TextObservation] = None
    allergens: Optional[TextObservation] = None
    nutrition: Optional[TextObservation] = None
    veg_non_veg: Optional[TextObservation] = None


class GeminiModelPayload(StrictGeminiModel):
    raw_visible_text: list[RawVisibleTextGroup] = Field(default_factory=list)
    context_suggestions: list[ContextSuggestion]
    declarations: StructuredDeclarationObservations
    uncertainty_flags: list[str]
    contradiction_flags: list[str]


class GeminiAuditMetadata(StrictGeminiModel):
    provider: Literal["GOOGLE_GEMINI"] = "GOOGLE_GEMINI"
    model: str
    schema_version: str
    prompt_version: str
    generated_at: datetime
    response_id: Optional[str] = None
    failure_code: Optional[str] = None


class GeminiPackageAnalysis(StrictGeminiModel):
    observation_layer: Literal["AI_OBSERVED"] = "AI_OBSERVED"
    status: GeminiAnalysisStatus
    raw_visible_text: list[RawVisibleTextGroup] = Field(default_factory=list)
    context_suggestions: list[ContextSuggestion] = Field(default_factory=list)
    declarations: StructuredDeclarationObservations = Field(default_factory=StructuredDeclarationObservations)
    uncertainty_flags: list[str] = Field(default_factory=list)
    contradiction_flags: list[str] = Field(default_factory=list)
    metadata: GeminiAuditMetadata


class GeminiCaptureEvidenceReference(StrictGeminiModel):
    capture_id: str = Field(..., min_length=1)
    view_id: str = Field(..., min_length=1)
    image_sha256: str = Field(..., min_length=64, max_length=64)


class GeminiPackageAuditRecord(StrictGeminiModel):
    """Append-only capture audit envelope outside compliance inputs."""

    audit_id: str = Field(..., min_length=1)
    inspection_id: str = Field(..., min_length=1)
    capture_evidence: list[GeminiCaptureEvidenceReference] = Field(..., min_length=1)
    analysis: GeminiPackageAnalysis
    created_at: datetime
    append_only: Literal[True] = True


class DetectedContextItem(StrictGeminiModel):
    field: str
    suggested_value: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class DetectedPackageContext(StrictGeminiModel):
    suggestion_layer: Literal["AI_SUGGESTED"] = "AI_SUGGESTED"
    suggestions: list[DetectedContextItem] = Field(default_factory=list)
    context_updates: dict[str, str] = Field(default_factory=dict)
    contradiction_fields: list[str] = Field(default_factory=list)
    ready_for_confirmation: bool = False
