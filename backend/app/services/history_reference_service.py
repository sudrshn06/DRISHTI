"""Read-only product identity matching for prior-inspection references."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.inspection import InspectionSession


PRODUCT_FIELDS = {"COMMON_GENERIC_NAME", "PRODUCT_NAME"}
BRAND_FIELDS = {"BRAND", "BRAND_NAME"}
BARCODE_FIELDS = {"BARCODE", "EAN", "GTIN", "UPC"}
BUSINESS_FIELD = "MANUFACTURER_PACKER_IMPORTER"


def _canonical(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def _candidate_value(candidate) -> str:
    normalized = candidate.normalized_value
    if hasattr(normalized, "model_dump"):
        normalized = normalized.model_dump(mode="json")
    if isinstance(normalized, dict):
        for key in ("name_text", "name", "code", "value", "raw_text"):
            if normalized.get(key):
                return str(normalized[key])
    if isinstance(normalized, str):
        return normalized
    return candidate.raw_value or ""


def inspection_identity(session: InspectionSession) -> dict[str, Any]:
    """Return stable stored identifiers without consulting AI legal conclusions."""
    products: set[str] = set()
    brands: set[str] = set()
    barcodes: set[str] = set()
    businesses: set[str] = set()
    display_product = None
    display_brand = None
    display_businesses: list[str] = []

    for candidate in session.aggregated_candidates:
        if candidate.status != "DETECTED":
            continue
        raw_value = _candidate_value(candidate)
        canonical = _canonical(raw_value)
        if not canonical:
            continue
        if candidate.field in PRODUCT_FIELDS:
            products.add(canonical)
            display_product = display_product or raw_value
        elif candidate.field in BRAND_FIELDS:
            brands.add(canonical)
            display_brand = display_brand or raw_value
        elif candidate.field in BARCODE_FIELDS:
            digits = re.sub(r"\D", "", raw_value)
            if len(digits) >= 8:
                barcodes.add(digits)
        elif candidate.field == BUSINESS_FIELD:
            businesses.add(canonical)
            if raw_value not in display_businesses:
                display_businesses.append(raw_value)

    return {
        "products": products,
        "brands": brands,
        "barcodes": barcodes,
        "businesses": businesses,
        "image_sha256": {
            capture.image_sha256 for capture in session.captures if capture.image_sha256
        },
        "display_product": display_product,
        "display_brand": display_brand,
        "display_businesses": display_businesses,
    }


def related_match_basis(current: InspectionSession, previous: InspectionSession) -> list[str]:
    """Match only strong exact identifiers; historical outcomes remain reference-only."""
    current_identity = inspection_identity(current)
    previous_identity = inspection_identity(previous)
    basis = []
    if current_identity["image_sha256"] & previous_identity["image_sha256"]:
        basis.append("IDENTICAL_IMAGE_EVIDENCE")
    if current_identity["barcodes"] & previous_identity["barcodes"]:
        basis.append("MATCHING_BARCODE")
    if (
        current_identity["products"] & previous_identity["products"]
        and current_identity["brands"] & previous_identity["brands"]
    ):
        basis.append("MATCHING_BRAND_AND_PRODUCT")
    if (
        current_identity["products"] & previous_identity["products"]
        and current_identity["businesses"] & previous_identity["businesses"]
    ):
        basis.append("MATCHING_PRODUCT_AND_BUSINESS")
    return basis
