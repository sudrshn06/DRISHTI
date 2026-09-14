import uuid
import math
import statistics
from typing import List, Dict, Optional, Any, Set, Tuple
from app.schemas.ocr import OcrLine, FieldCandidate
from app.schemas.image_quality import ImageQualityAssessment
from app.schemas.visual_assessment import (
    NormalizedBoundingBox,
    PixelBoundingBox,
    RegionGeometry,
    TextProminenceMetrics,
    VisualReadabilitySignal,
    DeclarationVisualAssessment,
    DeclarationProximityEvidence,
    CaptureVisualAssessmentSummary,
    VisualCheckType,
    VisualObservationStatus,
    InterferingEvidence,
    VisualFinding,
    VisualCheckCapability,
    VisualRuleEvaluationResult
)

def compute_region_geometry(
    polygons: List[List[List[float]]],
    image_width: int,
    image_height: int,
    edge_margin_px: float = 2.0
) -> Optional[RegionGeometry]:
    """
    Computes generic image-relative bounding box and boundary geometry for a set of OCR polygons.
    Returns None if no valid points are present or image dimensions are non-positive.
    """
    if image_width <= 0 or image_height <= 0:
        return None
        
    all_points = []
    for poly in polygons:
        if not poly or not isinstance(poly, list):
            continue
        for pt in poly:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                try:
                    x = float(pt[0])
                    y = float(pt[1])
                    if not math.isnan(x) and not math.isnan(y) and not math.isinf(x) and not math.isinf(y):
                        all_points.append((x, y))
                except (ValueError, TypeError):
                    continue
                    
    if not all_points:
        return None
        
    raw_x_min = min(pt[0] for pt in all_points)
    raw_y_min = min(pt[1] for pt in all_points)
    raw_x_max = max(pt[0] for pt in all_points)
    raw_y_max = max(pt[1] for pt in all_points)
    
    # Clamp to image boundaries for safe pixel coordinates
    x_min = max(0.0, min(float(image_width), raw_x_min))
    y_min = max(0.0, min(float(image_height), raw_y_min))
    x_max = max(0.0, min(float(image_width), raw_x_max))
    y_max = max(0.0, min(float(image_height), raw_y_max))
    
    width_px = max(0.0, x_max - x_min)
    height_px = max(0.0, y_max - y_min)
    area_px = width_px * height_px
    
    total_image_area = float(image_width * image_height)
    
    norm_x_min = max(0.0, min(1.0, x_min / image_width))
    norm_y_min = max(0.0, min(1.0, y_min / image_height))
    norm_x_max = max(0.0, min(1.0, x_max / image_width))
    norm_y_max = max(0.0, min(1.0, y_max / image_height))
    
    dist_left = x_min
    dist_top = y_min
    dist_right = max(0.0, float(image_width) - x_max)
    dist_bottom = max(0.0, float(image_height) - y_max)
    
    # Check if region intersects/touches image boundary (or raw coordinates extend outside)
    touches_edge = bool(
        dist_left <= edge_margin_px
        or dist_top <= edge_margin_px
        or dist_right <= edge_margin_px
        or dist_bottom <= edge_margin_px
        or raw_x_min < 0.0
        or raw_y_min < 0.0
        or raw_x_max > float(image_width)
        or raw_y_max > float(image_height)
    )
    
    return RegionGeometry(
        pixel_box=PixelBoundingBox(
            x_min=round(x_min, 2),
            y_min=round(y_min, 2),
            x_max=round(x_max, 2),
            y_max=round(y_max, 2),
            width_px=round(width_px, 2),
            height_px=round(height_px, 2),
            area_px=round(area_px, 2)
        ),
        normalized_box=NormalizedBoundingBox(
            x_min=round(norm_x_min, 4),
            y_min=round(norm_y_min, 4),
            x_max=round(norm_x_max, 4),
            y_max=round(norm_y_max, 4)
        ),
        image_width=image_width,
        image_height=image_height,
        width_ratio=round(min(1.0, width_px / image_width), 4),
        height_ratio=round(min(1.0, height_px / image_height), 4),
        area_ratio=round(min(1.0, area_px / total_image_area), 4),
        distance_to_edge_px={
            "left": round(dist_left, 2),
            "top": round(dist_top, 2),
            "right": round(dist_right, 2),
            "bottom": round(dist_bottom, 2)
        },
        touches_edge=touches_edge,
        edge_margin_threshold_px=edge_margin_px
    )

def compute_median_line_height(ocr_lines: List[OcrLine]) -> Optional[float]:
    """
    Computes the median height of detected OCR text lines in pixels.
    Returns None if no lines with valid geometry are detected.
    """
    heights = []
    for line in ocr_lines:
        if not line.polygon:
            continue
        y_coords = [pt[1] for pt in line.polygon if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(y_coords) >= 2:
            h = max(y_coords) - min(y_coords)
            if h > 0:
                heights.append(h)
                
    if not heights:
        return None
    return round(float(statistics.median(heights)), 2)

def compute_prominence_metrics(
    geometry: RegionGeometry,
    median_line_height_px: Optional[float] = None
) -> TextProminenceMetrics:
    """
    Computes image-relative prominence metrics.
    Strictly avoids physical millimeter calculations.
    """
    height_to_median_ratio = None
    if median_line_height_px and median_line_height_px > 0:
        height_to_median_ratio = round(geometry.pixel_box.height_px / median_line_height_px, 2)
        
    # Relative visual prominence signal
    if height_to_median_ratio is not None and height_to_median_ratio >= 2.0:
        signal = "DOMINANT"
    elif height_to_median_ratio is not None and height_to_median_ratio < 0.7:
        signal = "SUB_MEDIAN"
    elif geometry.area_ratio >= 0.05:
        signal = "DOMINANT"
    else:
        signal = "STANDARD"
        
    return TextProminenceMetrics(
        height_to_image_ratio=geometry.height_ratio,
        area_to_image_ratio=geometry.area_ratio,
        height_to_median_line_height_ratio=height_to_median_ratio,
        prominence_signal=signal
    )

def evaluate_readability(
    ocr_confidence: float,
    is_clipped: bool,
    quality_assessment: Optional[ImageQualityAssessment] = None
) -> VisualReadabilitySignal:
    """
    Separates capture-quality issues from declaration readability.
    Never equates bad photography or low OCR confidence with illegal printing.
    """
    reasons = []
    capture_quality_status = "ACCEPTABLE"
    
    if quality_assessment:
        capture_quality_status = quality_assessment.quality_status
        if quality_assessment.quality_status == "RETAKE_RECOMMENDED":
            if quality_assessment.reasons:
                reasons.extend(quality_assessment.reasons)
            else:
                reasons.append("Image quality is degraded; retake recommended for reliable verification.")
                
    if is_clipped:
        reasons.append("Declaration region touches or crosses image boundary; recapture recommended to ensure full declaration coverage.")
        
    if ocr_confidence < 0.8:
        reasons.append(f"OCR recognition confidence is low ({ocr_confidence:.2f}); manual inspector review required.")
        
    # Determine technical readability classification
    if capture_quality_status == "RETAKE_RECOMMENDED" or is_clipped:
        technical_readability = "NEEDS_RECAPTURE"
    elif ocr_confidence < 0.8:
        technical_readability = "REVIEW_REQUIRED"
    else:
        technical_readability = "EVALUABLE"
        if not reasons:
            reasons.append("Declaration visual evidence is clearly framed and evaluable.")
            
    quality_metrics = {}
    if quality_assessment:
        quality_metrics = {
            "blur_score": quality_assessment.blur_score,
            "brightness": quality_assessment.brightness,
            "glare_percentage": quality_assessment.glare_percentage,
        }

    return VisualReadabilitySignal(
        ocr_confidence=round(max(0.0, min(1.0, ocr_confidence)), 2),
        is_clipped=is_clipped,
        capture_quality_status=capture_quality_status,
        technical_readability=technical_readability,
        readability_reasons=reasons,
        quality_metrics=quality_metrics,
    )


def _relative_image_position(geometry: Optional[RegionGeometry]) -> Optional[str]:
    """Describe a region's image-relative location without asserting legal placement."""
    if not geometry:
        return None
    box = geometry.normalized_box
    horizontal = "LEFT" if (box.x_min + box.x_max) / 2 < 1 / 3 else (
        "RIGHT" if (box.x_min + box.x_max) / 2 > 2 / 3 else "CENTER"
    )
    vertical = "TOP" if (box.y_min + box.y_max) / 2 < 1 / 3 else (
        "BOTTOM" if (box.y_min + box.y_max) / 2 > 2 / 3 else "MIDDLE"
    )
    return f"{vertical}_{horizontal}"


def _proximity_evidence(
    assessment: DeclarationVisualAssessment,
    other: DeclarationVisualAssessment,
) -> Optional[DeclarationProximityEvidence]:
    """Return pairwise pixel geometry only; no grouping or compliance inference."""
    if not assessment.geometry or not other.geometry:
        return None
    box = assessment.geometry.pixel_box
    other_box = other.geometry.pixel_box
    center_x = (box.x_min + box.x_max) / 2
    center_y = (box.y_min + box.y_max) / 2
    other_x = (other_box.x_min + other_box.x_max) / 2
    other_y = (other_box.y_min + other_box.y_max) / 2
    dx = other_x - center_x
    dy = other_y - center_y
    overlaps_x = box.x_min <= other_box.x_max and other_box.x_min <= box.x_max
    overlaps_y = box.y_min <= other_box.y_max and other_box.y_min <= box.y_max
    if overlaps_x and overlaps_y:
        direction = "OVERLAPPING"
    elif abs(dx) >= abs(dy):
        direction = "RIGHT" if dx >= 0 else "LEFT"
    else:
        direction = "BELOW" if dy >= 0 else "ABOVE"
    gap_x = max(0.0, other_box.x_min - box.x_max, box.x_min - other_box.x_max)
    gap_y = max(0.0, other_box.y_min - box.y_max, box.y_min - other_box.y_max)
    edge_gap = math.hypot(gap_x, gap_y)
    diagonal = math.hypot(assessment.geometry.image_width, assessment.geometry.image_height)
    center_distance = math.hypot(dx, dy) / diagonal if diagonal else 0.0
    return DeclarationProximityEvidence(
        other_field=other.field,
        other_evidence_ids=other.evidence_ids,
        relative_direction=direction,
        center_distance_ratio=round(center_distance, 4),
        edge_gap_px=round(edge_gap, 2),
    )

def assess_declaration(
    field: str,
    evidence_ids: List[str],
    capture_id: str,
    view_id: str,
    raw_text: str,
    polygons: List[List[List[float]]],
    image_width: int,
    image_height: int,
    median_line_height_px: Optional[float],
    ocr_confidence: float,
    quality_assessment: Optional[ImageQualityAssessment] = None,
    edge_margin_px: float = 2.0
) -> DeclarationVisualAssessment:
    """
    Constructs a complete DeclarationVisualAssessment for a detected field declaration.
    """
    geometry = compute_region_geometry(polygons, image_width, image_height, edge_margin_px)
    
    is_clipped = geometry.touches_edge if geometry else False
    
    prominence = None
    if geometry:
        prominence = compute_prominence_metrics(geometry, median_line_height_px)
        
    readability = evaluate_readability(
        ocr_confidence=ocr_confidence,
        is_clipped=is_clipped,
        quality_assessment=quality_assessment
    )
    
    notes = []
    if geometry and geometry.touches_edge:
        notes.append("Framing warning: text is close to or intersects image boundary.")
    if prominence and prominence.prominence_signal == "DOMINANT":
        notes.append("Declaration appears visually prominent relative to surrounding package text.")
    if readability.technical_readability == "NEEDS_RECAPTURE":
        notes.append("Technical observation: photograph framing/sharpness requires recapture before definitive inspection.")
    elif readability.technical_readability == "REVIEW_REQUIRED":
        notes.append("Technical observation: text evidence requires visual verification.")
        
    valid_polygons = []
    for poly in polygons:
        if isinstance(poly, list):
            valid_pts = []
            for pt in poly:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    try:
                        x = float(pt[0])
                        y = float(pt[1])
                        if not math.isnan(x) and not math.isnan(y) and not math.isinf(x) and not math.isinf(y):
                            valid_pts.append([x, y])
                    except (ValueError, TypeError):
                        continue
            if valid_pts:
                valid_polygons.append(valid_pts)

    return DeclarationVisualAssessment(
        field=field,
        evidence_ids=evidence_ids,
        capture_id=capture_id,
        view_id=view_id,
        raw_text=raw_text,
        polygons=valid_polygons,
        geometry=geometry,
        prominence=prominence,
        relative_position_in_image=_relative_image_position(geometry),
        readability=readability,
        technical_status=readability.technical_readability,
        notes=notes
    )

def evaluate_net_quantity_clearance(
    nq_assessment: DeclarationVisualAssessment,
    ocr_lines: List[OcrLine],
    evidence_map: Dict[str, str],
    image_width: int,
    image_height: int,
    quality_assessment: Optional[ImageQualityAssessment] = None
) -> VisualFinding:
    """
    Evaluates Rule 8 surrounding clearance for Net Quantity declaration:
    - Vertical clearance: 1x reference text height (above and below)
    - Horizontal clearance: 2x reference text height (left and right)
    Excludes the Net Quantity declaration itself and detects intersecting surrounding OCR text.
    """
    finding_id = f"finding_nq_clearance_{nq_assessment.capture_id[:8]}"
    legal_ref = "Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 8(1)"
    
    # 1. Image quality gating
    if quality_assessment and quality_assessment.quality_status == "RETAKE_RECOMMENDED":
        return VisualFinding(
            finding_id=finding_id,
            check_type=VisualCheckType.NET_QUANTITY_CLEARANCE,
            field="NET_QUANTITY",
            capture_id=nq_assessment.capture_id,
            view_id=nq_assessment.view_id,
            evidence_ids=nq_assessment.evidence_ids,
            status=VisualObservationStatus.NEEDS_RECAPTURE,
            metrics={"reason_type": "POOR_CAPTURE_QUALITY"},
            reason="Image quality is degraded; photograph recapture required before surrounding clearance can be evaluated.",
            legal_reference=legal_ref,
            limitations="Clearance evaluation requires an in-focus and evenly lit photograph."
        )
        
    # 2. Geometry availability
    if not nq_assessment.geometry or not nq_assessment.geometry.pixel_box:
        return VisualFinding(
            finding_id=finding_id,
            check_type=VisualCheckType.NET_QUANTITY_CLEARANCE,
            field="NET_QUANTITY",
            capture_id=nq_assessment.capture_id,
            view_id=nq_assessment.view_id,
            evidence_ids=nq_assessment.evidence_ids,
            status=VisualObservationStatus.NOT_EVALUABLE,
            metrics={"reason_type": "MISSING_GEOMETRY"},
            reason="Net quantity declaration geometry is not available to calculate clearance boundaries.",
            legal_reference=legal_ref,
            limitations="Bounding box coordinates could not be derived from OCR evidence."
        )
        
    pb = nq_assessment.geometry.pixel_box
    H = pb.height_px
    if H <= 0:
        return VisualFinding(
            finding_id=finding_id,
            check_type=VisualCheckType.NET_QUANTITY_CLEARANCE,
            field="NET_QUANTITY",
            capture_id=nq_assessment.capture_id,
            view_id=nq_assessment.view_id,
            evidence_ids=nq_assessment.evidence_ids,
            status=VisualObservationStatus.NOT_EVALUABLE,
            metrics={"reason_type": "ZERO_HEIGHT"},
            reason="Net quantity declaration has zero text height.",
            legal_reference=legal_ref
        )
        
    # Clearance zone boundaries:
    # Vertical: 1x H (top: y_min - H, bottom: y_max + H)
    # Horizontal: 2x H (left: x_min - 2H, right: x_max + 2H)
    c_x_min = pb.x_min - (2.0 * H)
    c_y_min = pb.y_min - (1.0 * H)
    c_x_max = pb.x_max + (2.0 * H)
    c_y_max = pb.y_max + (1.0 * H)
    
    metrics = {
        "declaration_box_px": {"x_min": pb.x_min, "y_min": pb.y_min, "x_max": pb.x_max, "y_max": pb.y_max},
        "reference_height_type": "DECLARATION_LINE_HEIGHT",
        "is_numeral_geometry_isolated": False,
        "reference_text_height_px": H,
        "vertical_clearance_required_px": round(H, 2),
        "horizontal_clearance_required_px": round(2.0 * H, 2),
        "clearance_box_px": {
            "x_min": round(c_x_min, 2),
            "y_min": round(c_y_min, 2),
            "x_max": round(c_x_max, 2),
            "y_max": round(c_y_max, 2)
        }
    }
    
    # 3. Check if clearance zone extends outside image frame
    extends_outside = (c_x_min < 0.0 or c_y_min < 0.0 or c_x_max > float(image_width) or c_y_max > float(image_height))
    if extends_outside:
        metrics["clearance_extends_outside_image"] = True
        return VisualFinding(
            finding_id=finding_id,
            check_type=VisualCheckType.NET_QUANTITY_CLEARANCE,
            field="NET_QUANTITY",
            capture_id=nq_assessment.capture_id,
            view_id=nq_assessment.view_id,
            evidence_ids=nq_assessment.evidence_ids,
            status=VisualObservationStatus.NEEDS_RECAPTURE,
            metrics=metrics,
            reason="Net quantity approximate Rule 8 clearance zone (1x height vertical, 2x height horizontal) extends beyond image boundaries; recapture with wider framing recommended.",
            legal_reference=legal_ref,
            limitations="Full surrounding package area must be visible in the image to verify statutory clearance."
        )
        
    # 4. Search for interfering OCR lines within the clearance zone (excluding Net Quantity itself)
    nq_evidence_set = set(nq_assessment.evidence_ids)
    nq_line_indices = {int(idx_str) for idx_str, ev_id in evidence_map.items() if ev_id in nq_evidence_set}
    
    interfering_list: List[InterferingEvidence] = []
    
    for i, line in enumerate(ocr_lines):
        if i in nq_line_indices or not line.polygon:
            continue
            
        # Get line bbox
        l_pts = [pt for pt in line.polygon if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if not l_pts:
            continue
        lx_min = min(pt[0] for pt in l_pts)
        ly_min = min(pt[1] for pt in l_pts)
        lx_max = max(pt[0] for pt in l_pts)
        ly_max = max(pt[1] for pt in l_pts)
        
        # Check if line substantially overlaps Net Quantity declaration itself (duplicate fragment)
        nq_overlap_w = max(0.0, min(lx_max, pb.x_max) - max(lx_min, pb.x_min))
        nq_overlap_h = max(0.0, min(ly_max, pb.y_max) - max(ly_min, pb.y_min))
        nq_overlap_area = nq_overlap_w * nq_overlap_h
        line_area = max(1.0, (lx_max - lx_min) * (ly_max - ly_min))
        
        if (nq_overlap_area / line_area) > 0.7:
            # Belongs to net quantity fragment, ignore
            continue
            
        # Check intersection with clearance box
        ix_min = max(lx_min, c_x_min)
        iy_min = max(ly_min, c_y_min)
        ix_max = min(lx_max, c_x_max)
        iy_max = min(ly_max, c_y_max)
        
        if ix_max > ix_min and iy_max > iy_min:
            inter_area = (ix_max - ix_min) * (iy_max - iy_min)
            # Ensure intersection is in the surrounding zone (outside NQ box itself)
            if inter_area > 4.0: # Ignore sub-pixel / negligible touches
                interfering_list.append(
                    InterferingEvidence(
                        text=line.text,
                        confidence=round(line.confidence, 2),
                        polygon=line.polygon,
                        evidence_id=evidence_map.get(str(i)),
                        intersection_area_px=round(inter_area, 2)
                    )
                )
                
    if interfering_list:
        metrics["interfering_count"] = len(interfering_list)
        return VisualFinding(
            finding_id=finding_id,
            check_type=VisualCheckType.NET_QUANTITY_CLEARANCE,
            field="NET_QUANTITY",
            capture_id=nq_assessment.capture_id,
            view_id=nq_assessment.view_id,
            evidence_ids=nq_assessment.evidence_ids,
            status=VisualObservationStatus.REVIEW_REQUIRED,
            metrics=metrics,
            reason=f"Detected {len(interfering_list)} intersecting text element(s) within the approximate Rule 8 clearance zone based on declaration line height. Inspector review required.",
            legal_reference=legal_ref,
            limitations="Interference observation is based on 2D image coordinates and OCR declaration line bounding box.",
            interfering_evidence=interfering_list
        )
    else:
        return VisualFinding(
            finding_id=finding_id,
            check_type=VisualCheckType.NET_QUANTITY_CLEARANCE,
            field="NET_QUANTITY",
            capture_id=nq_assessment.capture_id,
            view_id=nq_assessment.view_id,
            evidence_ids=nq_assessment.evidence_ids,
            status=VisualObservationStatus.REVIEW_REQUIRED,
            metrics=metrics,
            reason=f"Surrounding zone appears clear of intersecting text based on full declaration line height ({H:.1f}px). Statutory Rule 8 clearance is legally referenced to isolated numeral height; inspector visual confirmation required.",
            legal_reference=legal_ref,
            limitations="OCR bounding box represents the full declaration line (e.g. including prefix and units). Exact numeral-level clearance geometry is not isolated without token-level segmentation."
        )

def generate_all_visual_findings(
    capture_id: str,
    view_id: str,
    image_width: int,
    image_height: int,
    assessments: List[DeclarationVisualAssessment],
    ocr_lines: List[OcrLine],
    evidence_map: Dict[str, str],
    quality_assessment: Optional[ImageQualityAssessment],
    median_line_height: Optional[float]
) -> List[VisualFinding]:
    """
    Generates structured, deduplicated inspector findings for placement, readability,
    clipping, and statutory boundary limitations.
    """
    findings: List[VisualFinding] = []
    is_poor_quality = quality_assessment and quality_assessment.quality_status == "RETAKE_RECOMMENDED"
    
    # 1. Clipping and Framing Checks
    if is_poor_quality:
        findings.append(
            VisualFinding(
                finding_id=f"finding_capture_quality_{capture_id[:8]}",
                check_type=VisualCheckType.CLIPPING_AND_FRAMING,
                capture_id=capture_id,
                view_id=view_id,
                status=VisualObservationStatus.NEEDS_RECAPTURE,
                metrics={
                    "blur_score": quality_assessment.blur_score,
                    "glare_percentage": quality_assessment.glare_percentage,
                    "brightness": quality_assessment.brightness
                },
                reason="Photograph quality is degraded (blur, glare, or poor lighting); recapture recommended for reliable visual verification.",
                limitations="Non-accusatory photographic quality observation; does not imply packaging non-compliance."
            )
        )
    else:
        for a in assessments:
            if a.geometry and a.geometry.touches_edge:
                findings.append(
                    VisualFinding(
                        finding_id=f"finding_clipping_{a.field}_{capture_id[:8]}",
                        check_type=VisualCheckType.CLIPPING_AND_FRAMING,
                        field=a.field,
                        capture_id=capture_id,
                        view_id=view_id,
                        evidence_ids=a.evidence_ids,
                        status=VisualObservationStatus.NEEDS_RECAPTURE,
                        metrics={"distance_to_edge_px": a.geometry.distance_to_edge_px},
                        reason=f"Declaration '{a.field}' touches or intersects the image boundary; recapture recommended to ensure complete text coverage.",
                        limitations="Evidence insufficiency observation; does not constitute a statutory printing violation."
                    )
                )
                
    # 2. Net Quantity Clearance Check (Rule 8)
    nq_assessment = next((a for a in assessments if a.field == "NET_QUANTITY"), None)
    if nq_assessment:
        nq_finding = evaluate_net_quantity_clearance(
            nq_assessment=nq_assessment,
            ocr_lines=ocr_lines,
            evidence_map=evidence_map,
            image_width=image_width,
            image_height=image_height,
            quality_assessment=quality_assessment
        )
        findings.append(nq_finding)
        
    # 3. Readability & Prominence Checks (Suppressed if capture is degraded to prevent redundant noise)
    if not is_poor_quality:
        for a in assessments:
            # Readability
            if a.readability.ocr_confidence < 0.8:
                findings.append(
                    VisualFinding(
                        finding_id=f"finding_readability_{a.field}_{capture_id[:8]}",
                        check_type=VisualCheckType.READABILITY,
                        field=a.field,
                        capture_id=capture_id,
                        view_id=view_id,
                        evidence_ids=a.evidence_ids,
                        status=VisualObservationStatus.REVIEW_REQUIRED,
                        metrics={"ocr_confidence": a.readability.ocr_confidence},
                        reason=f"OCR recognition confidence for '{a.field}' is {a.readability.ocr_confidence:.2f} (< 0.80); visual inspector confirmation required.",
                        limitations="Machine OCR confidence is an assistive heuristic and does not prove statutory illegibility."
                    )
                )
            else:
                findings.append(
                    VisualFinding(
                        finding_id=f"finding_readability_{a.field}_{capture_id[:8]}",
                        check_type=VisualCheckType.READABILITY,
                        field=a.field,
                        capture_id=capture_id,
                        view_id=view_id,
                        evidence_ids=a.evidence_ids,
                        status=VisualObservationStatus.OBSERVATION_CLEAR,
                        metrics={"ocr_confidence": a.readability.ocr_confidence},
                        reason=f"Declaration '{a.field}' is clearly readable with high OCR recognition confidence ({a.readability.ocr_confidence:.2f})."
                    )
                )
                
            # Relative Prominence
            if a.prominence and a.prominence.prominence_signal == "SUB_MEDIAN":
                findings.append(
                    VisualFinding(
                        finding_id=f"finding_prominence_{a.field}_{capture_id[:8]}",
                        check_type=VisualCheckType.RELATIVE_PROMINENCE,
                        field=a.field,
                        capture_id=capture_id,
                        view_id=view_id,
                        evidence_ids=a.evidence_ids,
                        status=VisualObservationStatus.REVIEW_REQUIRED,
                        metrics={
                            "height_to_median_ratio": a.prominence.height_to_median_line_height_ratio,
                            "declaration_height_px": a.geometry.pixel_box.height_px if a.geometry else None,
                            "median_line_height_px": median_line_height
                        },
                        reason=f"Declaration '{a.field}' text height is smaller than median detected package text ({a.prominence.height_to_median_line_height_ratio:.2f}x median). Inspector review recommended for visual prominence.",
                        limitations="Relative prominence is an image-relative heuristic and does not measure physical millimetre font height."
                    )
                )
            elif a.prominence:
                findings.append(
                    VisualFinding(
                        finding_id=f"finding_prominence_{a.field}_{capture_id[:8]}",
                        check_type=VisualCheckType.RELATIVE_PROMINENCE,
                        field=a.field,
                        capture_id=capture_id,
                        view_id=view_id,
                        evidence_ids=a.evidence_ids,
                        status=VisualObservationStatus.OBSERVATION_CLEAR,
                        metrics={
                            "height_to_median_ratio": a.prominence.height_to_median_line_height_ratio,
                            "prominence_signal": a.prominence.prominence_signal
                        },
                        reason=f"Declaration '{a.field}' has standard or dominant visual prominence relative to surrounding text."
                    )
                )
                
    # 4. Statutory Boundary Limitations (Explicitly Documented)
    font_measurements = [
        {
            "field": item.field,
            "view_id": item.view_id,
            "bbox_height_px": item.geometry.pixel_box.height_px,
            "height_to_image_ratio": item.prominence.height_to_image_ratio if item.prominence else None,
            "height_to_median_line_height_ratio": (
                item.prominence.height_to_median_line_height_ratio if item.prominence else None
            ),
            "ocr_confidence": item.readability.ocr_confidence,
        }
        for item in assessments if item.geometry
    ]
    findings.append(
        VisualFinding(
            finding_id=f"finding_statutory_rule7_{capture_id[:8]}",
            check_type=VisualCheckType.PHYSICAL_FONT_SIZE_RULE_7,
            capture_id=capture_id,
            view_id=view_id,
            status=(
                VisualObservationStatus.REVIEW_REQUIRED
                if font_measurements else VisualObservationStatus.NOT_EVALUABLE
            ),
            metrics={
                "physical_scale_available": False,
                "relative_text_measurements": font_measurements,
            },
            reason="Statutory minimum numeral and letter heights in millimetres under Rule 7 cannot be deterministically evaluated from uncalibrated digital images without a trusted physical scale reference.",
            legal_reference="Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 7",
            limitations="DRISHTI strictly prohibits converting pixel dimensions to millimetres or inferring physical packaging dimensions from digital images."
        )
    )
    
    placement_measurements = [
        {
            "field": item.field,
            "view_id": item.view_id,
            "normalized_box": item.geometry.normalized_box.model_dump(mode="json"),
            "relative_position_in_image": item.relative_position_in_image,
            "proximity_to_declarations": [
                proximity.model_dump(mode="json") for proximity in item.proximity_to_declarations
            ],
        }
        for item in assessments if item.geometry
    ]
    findings.append(
        VisualFinding(
            finding_id=f"finding_statutory_contrast_{capture_id[:8]}",
            check_type=VisualCheckType.CONTRAST_RULE_9,
            capture_id=capture_id,
            view_id=view_id,
            status=VisualObservationStatus.NOT_EVALUABLE,
            reason="Definitive colour contrast verification under Rule 9(1)(a) requires controlled lighting and spectrophotometric calibration; uncalibrated camera RGB values are not used for legal non-compliance.",
            legal_reference="Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 9(1)(a)",
            limitations="Machine OCR confidence is not used as legal evidence of printing contrast."
        )
    )
    
    findings.append(
        VisualFinding(
            finding_id=f"finding_statutory_pdp_{capture_id[:8]}",
            check_type=VisualCheckType.PRINCIPAL_DISPLAY_PANEL_RULE_8,
            capture_id=capture_id,
            view_id=view_id,
            status=(
                VisualObservationStatus.REVIEW_REQUIRED
                if placement_measurements else VisualObservationStatus.NOT_EVALUABLE
            ),
            metrics={"measured_image_placement": placement_measurements},
            reason=f"Captured view '{view_id}' represents a camera view role and is not automatically classified as the statutory Principal Display Panel without surface area context.",
            legal_reference="Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 8",
            limitations="Camera view roles (e.g. FRONT) are strictly separated from statutory Principal Display Panel determinations."
        )
    )
    
    return findings

def assess_capture_visuals(
    capture_id: str,
    view_id: str,
    image_width: int,
    image_height: int,
    ocr_lines: List[OcrLine],
    field_candidates: List[FieldCandidate],
    evidence_map: Dict[str, str],
    quality_assessment: Optional[ImageQualityAssessment] = None
) -> CaptureVisualAssessmentSummary:
    """
    Evaluates visual evidence for all extracted candidates across a capture.
    Maps candidate evidence IDs back to OCR lines and polygons, and computes structured findings.
    """
    # Invert evidence_map: evidence_id -> line_idx
    ev_to_line_idx = {ev_id: int(line_idx_str) for line_idx_str, ev_id in evidence_map.items()}
    
    median_line_height = compute_median_line_height(ocr_lines)
    
    assessments: List[DeclarationVisualAssessment] = []
    has_clipped = False
    
    for cand in field_candidates:
        if cand.status not in ("DETECTED", "REVIEW_REQUIRED"):
            continue
            
        cand_polygons = []
        cand_texts = []
        cand_confidences = []
        
        for ev_id in cand.evidence_ids:
            if ev_id in ev_to_line_idx:
                line_idx = ev_to_line_idx[ev_id]
                if 0 <= line_idx < len(ocr_lines):
                    line = ocr_lines[line_idx]
                    if line.polygon:
                        cand_polygons.append(line.polygon)
                    cand_texts.append(line.text)
                    cand_confidences.append(line.confidence)
                    
        raw_text = cand.raw_value or ("\n".join(cand_texts) if cand_texts else "")
        confidence = cand.confidence if cand.confidence is not None else (
            sum(cand_confidences) / len(cand_confidences) if cand_confidences else 0.9
        )
        
        assessment = assess_declaration(
            field=cand.field,
            evidence_ids=cand.evidence_ids,
            capture_id=capture_id,
            view_id=view_id,
            raw_text=raw_text,
            polygons=cand_polygons,
            image_width=image_width,
            image_height=image_height,
            median_line_height_px=median_line_height,
            ocr_confidence=confidence,
            quality_assessment=quality_assessment
        )
        
        if assessment.readability.is_clipped:
            has_clipped = True
            
        assessments.append(assessment)

    # Attach pairwise measurements only after every declaration region on this
    # surface has been constructed. These are descriptive coordinates, not a
    # legal grouping or placement rule.
    for assessment in assessments:
        assessment.proximity_to_declarations = [
            proximity
            for other in assessments
            if other is not assessment
            for proximity in [_proximity_evidence(assessment, other)]
            if proximity is not None
        ]
        
    findings = generate_all_visual_findings(
        capture_id=capture_id,
        view_id=view_id,
        image_width=image_width,
        image_height=image_height,
        assessments=assessments,
        ocr_lines=ocr_lines,
        evidence_map=evidence_map,
        quality_assessment=quality_assessment,
        median_line_height=median_line_height
    )
    
    # Aggregate overall visual status
    if any(f.status == VisualObservationStatus.NEEDS_RECAPTURE for f in findings):
        overall_status = "NEEDS_RECAPTURE"
    elif any(f.status == VisualObservationStatus.REVIEW_REQUIRED for f in findings):
        overall_status = "REVIEW_REQUIRED"
    else:
        overall_status = "EVALUABLE"
        
    return CaptureVisualAssessmentSummary(
        capture_id=capture_id,
        view_id=view_id,
        image_width=image_width,
        image_height=image_height,
        total_detected_lines=len(ocr_lines),
        median_line_height_px=median_line_height,
        assessments=assessments,
        findings=findings,
        has_clipped_declarations=has_clipped,
        overall_visual_status=overall_status
    )

def evaluate_visual_legal_rules(
    captures: List[Any],
    aggregated_candidates: List[FieldCandidate],
    reference_date: Optional[Any] = None
) -> List[VisualRuleEvaluationResult]:
    """
    Constructs deterministic legal evaluations for Rule 7, Rule 8, and Rule 9 visual boundaries.
    Maintains clean separation from declaration presence rules.
    """
    results: List[VisualRuleEvaluationResult] = []
    
    # Collect all findings, evidence_ids, capture_ids
    all_findings: List[VisualFinding] = []
    all_evidence_ids: Set[str] = set()
    all_capture_ids: List[str] = []
    has_poor_capture = False
    
    for cap in captures:
        all_capture_ids.append(cap.capture_id)
        if cap.quality_assessment and cap.quality_assessment.quality_status == "RETAKE_RECOMMENDED":
            has_poor_capture = True
        if cap.visual_assessment:
            all_findings.extend(cap.visual_assessment.findings)
            for a in cap.visual_assessment.assessments:
                all_evidence_ids.update(a.evidence_ids)
                
    ev_list = sorted(list(all_evidence_ids))
    
    # 1. RULE 7: Minimum Numeral & Letter Height
    r7_findings = [f.finding_id for f in all_findings if f.check_type == VisualCheckType.PHYSICAL_FONT_SIZE_RULE_7]
    r7_measurements = [
        measurement
        for finding in all_findings
        if finding.check_type == VisualCheckType.PHYSICAL_FONT_SIZE_RULE_7
        for measurement in finding.metrics.get("relative_text_measurements", [])
    ]
    results.append(
        VisualRuleEvaluationResult(
            rule_id="RULE_7_MINIMUM_NUMERAL_HEIGHT",
            legal_reference="Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 7 & Second Schedule",
            field="ALL_DECLARATIONS",
            capability=VisualCheckCapability.NOT_EVALUABLE_FROM_CURRENT_CAPTURE,
            status="REVIEW_REQUIRED" if r7_measurements else "NOT_EVALUABLE",
            requires_inspector_review=True,
            evidence_ids=ev_list,
            capture_ids=all_capture_ids,
            supporting_visual_findings=r7_findings,
            metrics={
                "requires_physical_scale_reference": True,
                "relative_text_measurements": r7_measurements,
            },
            reason="Statutory minimum numeral and letter heights in millimetres under Rule 7 cannot be deterministically verified from camera images without a trusted physical scale reference and principal display panel area measurement.",
            limitations="DRISHTI strictly prohibits converting pixel dimensions to millimetres or estimating physical packaging dimensions from digital images."
        )
    )
    
    # 2. RULE 8: Principal Display Panel Placement
    r8_pdp_findings = [f.finding_id for f in all_findings if f.check_type == VisualCheckType.PRINCIPAL_DISPLAY_PANEL_RULE_8]
    r8_placement_measurements = [
        measurement
        for finding in all_findings
        if finding.check_type == VisualCheckType.PRINCIPAL_DISPLAY_PANEL_RULE_8
        for measurement in finding.metrics.get("measured_image_placement", [])
    ]
    results.append(
        VisualRuleEvaluationResult(
            rule_id="RULE_8_PRINCIPAL_DISPLAY_PANEL_PLACEMENT",
            legal_reference="Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 8",
            field="ALL_DECLARATIONS",
            capability=VisualCheckCapability.NOT_EVALUABLE_FROM_CURRENT_CAPTURE,
            status="REVIEW_REQUIRED" if r8_placement_measurements else "NOT_EVALUABLE",
            requires_inspector_review=True,
            evidence_ids=ev_list,
            capture_ids=all_capture_ids,
            supporting_visual_findings=r8_pdp_findings,
            metrics={
                "view_roles_present": [c.view_id for c in captures],
                "measured_image_placement": r8_placement_measurements,
            },
            reason="Photographed view roles (e.g. FRONT) represent camera perspectives and are not automatically classified as the statutory Principal Display Panel without surface area context.",
            limitations="Camera view roles are strictly separated from statutory Principal Display Panel determinations."
        )
    )
    
    # 3. RULE 8: Net Quantity Surrounding Clearance
    r8_nq_findings = [f for f in all_findings if f.check_type == VisualCheckType.NET_QUANTITY_CLEARANCE]
    nq_cand = next((c for c in aggregated_candidates if c.field == "NET_QUANTITY"), None)
    
    if not nq_cand or nq_cand.status not in ("DETECTED", "REVIEW_REQUIRED"):
        nq_status = "NOT_APPLICABLE"
        nq_reason = "Net quantity declaration is not detected in current captures."
    elif has_poor_capture or any(f.status == VisualObservationStatus.NEEDS_RECAPTURE for f in r8_nq_findings):
        nq_status = "REVIEW_REQUIRED"
        nq_reason = "Net quantity surrounding clearance could not be fully verified due to photograph framing or quality limitations; recapture recommended."
    elif any(f.status == VisualObservationStatus.REVIEW_REQUIRED and f.interfering_evidence for f in r8_nq_findings):
        nq_status = "REVIEW_REQUIRED"
        inter_count = sum(len(f.interfering_evidence) for f in r8_nq_findings)
        nq_reason = f"Detected {inter_count} potential intersecting text element(s) in the approximate surrounding clearance zone based on declaration line height. Inspector review required."
    else:
        nq_status = "REVIEW_REQUIRED"
        nq_reason = "Surrounding zone appears clear of intersecting text based on declaration line height. Statutory Rule 8 clearance is legally referenced to isolated numeral height; inspector visual confirmation required."
        
    results.append(
        VisualRuleEvaluationResult(
            rule_id="RULE_8_NET_QUANTITY_SURROUNDING_CLEARANCE",
            legal_reference="Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 8(1)",
            field="NET_QUANTITY",
            capability=VisualCheckCapability.INSPECTOR_REVIEW_ONLY,
            status=nq_status,
            requires_inspector_review=True,
            evidence_ids=nq_cand.evidence_ids if nq_cand else [],
            capture_ids=all_capture_ids,
            supporting_visual_findings=[f.finding_id for f in r8_nq_findings],
            metrics={"is_numeral_geometry_isolated": False},
            reason=nq_reason,
            limitations="OCR bounding box represents the full declaration line. Exact statutory numeral-level clearance geometry is not isolated without token-level segmentation."
        )
    )
    
    # 4. RULE 9: Declaration Legibility / Readability
    r9_read_findings = [f for f in all_findings if f.check_type == VisualCheckType.READABILITY]
    results.append(
        VisualRuleEvaluationResult(
            rule_id="RULE_9_DECLARATION_LEGIBILITY",
            legal_reference="Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 9(1)(a)",
            field="ALL_DECLARATIONS",
            capability=VisualCheckCapability.INSPECTOR_REVIEW_ONLY,
            status="REVIEW_REQUIRED",
            requires_inspector_review=True,
            evidence_ids=ev_list,
            capture_ids=all_capture_ids,
            supporting_visual_findings=[f.finding_id for f in r9_read_findings],
            metrics={"total_declarations_evaluated": len(r9_read_findings)},
            reason="Machine OCR confidence and blur metrics provide assistive readability signals to aid inspector review, but do not constitute statutory proof of legibility or illegibility under Rule 9(1)(a).",
            limitations="Low or high OCR confidence is an assistive technical signal and never produces an automated statutory FAIL or unconditional PASS."
        )
    )
    
    # 5. RULE 9: Relative Visual Prominence
    r9_prom_findings = [f for f in all_findings if f.check_type == VisualCheckType.RELATIVE_PROMINENCE]
    results.append(
        VisualRuleEvaluationResult(
            rule_id="RULE_9_RELATIVE_PROMINENCE",
            legal_reference="Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 9(1)(a)",
            field="ALL_DECLARATIONS",
            capability=VisualCheckCapability.INSPECTOR_REVIEW_ONLY,
            status="REVIEW_REQUIRED",
            requires_inspector_review=True,
            evidence_ids=ev_list,
            capture_ids=all_capture_ids,
            supporting_visual_findings=[f.finding_id for f in r9_prom_findings],
            metrics={"total_prominence_evaluations": len(r9_prom_findings)},
            reason="Relative prominence metrics (DOMINANT, STANDARD, SUB_MEDIAN) compare declaration height to median image text as an engineering heuristic to assist inspector review.",
            limitations="Relative prominence is an image-relative heuristic and does not measure physical millimetre font height."
        )
    )
    
    # 6. RULE 9: Colour Contrast
    r9_contrast_findings = [f.finding_id for f in all_findings if f.check_type == VisualCheckType.CONTRAST_RULE_9]
    results.append(
        VisualRuleEvaluationResult(
            rule_id="RULE_9_COLOUR_CONTRAST",
            legal_reference="Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 9(1)(a)",
            field="ALL_DECLARATIONS",
            capability=VisualCheckCapability.NOT_EVALUABLE_FROM_CURRENT_CAPTURE,
            status="NOT_EVALUABLE",
            requires_inspector_review=True,
            evidence_ids=ev_list,
            capture_ids=all_capture_ids,
            supporting_visual_findings=r9_contrast_findings,
            metrics={"requires_spectrophotometric_calibration": True},
            reason="Definitive colour contrast verification under Rule 9(1)(a) requires controlled lighting and spectrophotometric calibration; uncalibrated camera RGB values are not used for legal non-compliance.",
            limitations="Machine OCR confidence is not used as legal evidence of printing contrast."
        )
    )
    
    return results
