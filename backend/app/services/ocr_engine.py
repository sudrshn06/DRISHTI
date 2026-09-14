import logging
import os
import threading
from importlib.metadata import PackageNotFoundError, version
from typing import List

import cv2
import numpy as np
from fastapi import HTTPException, status
from app.schemas.ocr import OcrLine

logger = logging.getLogger(__name__)

# Keep construction lazy: importing the application must not allocate OCR models.
_ocr_model = None
_ocr_model_lock = threading.Lock()
_OCR_MAX_SIDE = 1800
OCR_PREPROCESSING_CONFIG_ID = "drishti-ocr-preprocess-v1:max-side=1800:inter-area"


def get_ocr_engine_version() -> str:
    """Return the installed provider version without constructing its models."""
    try:
        return version("paddleocr")
    except PackageNotFoundError:
        return "UNKNOWN"


def canonicalize_ocr_lines(lines: List[OcrLine]) -> List[OcrLine]:
    """Return a stable visual reading order independent of provider list order."""
    def line_key(line: OcrLine):
        xs = [point[0] for point in line.polygon] or [0.0]
        ys = [point[1] for point in line.polygon] or [0.0]
        return (
            round(min(ys), 4),
            round(min(xs), 4),
            round(max(ys), 4),
            round(max(xs), 4),
            line.text,
        )

    return [line.model_copy(deep=True) for line in sorted(lines, key=line_key)]

def get_ocr_model():
    global _ocr_model
    if _ocr_model is None:
        with _ocr_model_lock:
            if _ocr_model is None:
                try:
                    os.environ["FLAGS_use_mkldnn"] = "0"
                    from paddleocr import PaddleOCR
                    # Configure PaddleOCR for Phase 1: CPU, English, minimal doc orientation processing
                    _ocr_model = PaddleOCR(
                        use_angle_cls=False,
                        lang="en",
                        device="cpu",
                        use_doc_orientation_classify=False,
                        use_doc_unwarping=False,
                        enable_mkldnn=False
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize PaddleOCR: {e}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail={"error": {"code": "OCR_PROCESSING_FAILED", "message": "OCR engine initialization failed."}}
                    )
    return _ocr_model


def _prepare_ocr_image(image: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Return an isolated inference copy and coordinate scales to the source."""
    original_height, original_width = image.shape[:2]
    max_side = max(original_width, original_height)
    if max_side <= _OCR_MAX_SIDE:
        return image.copy(), 1.0, 1.0

    resize_ratio = _OCR_MAX_SIDE / max_side
    working_width = max(1, round(original_width * resize_ratio))
    working_height = max(1, round(original_height * resize_ratio))
    working_image = cv2.resize(
        image,
        (working_width, working_height),
        interpolation=cv2.INTER_AREA,
    )
    return (
        working_image,
        original_width / working_width,
        original_height / working_height,
    )

def analyze_image(image: np.ndarray) -> List[OcrLine]:
    """
    Runs PaddleOCR on the decoded image and returns structured lines.
    Raises HTTPException with NO_USABLE_TEXT_DETECTED or OCR_PROCESSING_FAILED.
    """
    ocr = get_ocr_model()
    working_image, scale_x, scale_y = _prepare_ocr_image(image)
    
    try:
        # result is a list of lists: [[[ [x,y],[x,y],[x,y],[x,y] ], ("text", confidence)], ...]
        # Note: result can have multiple lists for multiple text boxes, 
        # usually result[0] contains the actual list of detections.
        result = ocr.ocr(working_image)
    except Exception as e:
        logger.error(f"PaddleOCR execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "OCR_PROCESSING_FAILED", "message": "OCR engine execution failed."}}
        )

    if not result or not isinstance(result, list) or not result[0]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "NO_USABLE_TEXT_DETECTED", "message": "PaddleOCR executed successfully but found no usable text."}}
        )

    lines = []
    res_dict = result[0]
    
    # In PaddleOCR 3.7.0, the output is a dict with rec_texts, rec_scores, dt_polys
    texts = res_dict.get('rec_texts', [])
    scores = res_dict.get('rec_scores', [])
    polys = res_dict.get('dt_polys', [])
    
    if not texts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "NO_USABLE_TEXT_DETECTED", "message": "PaddleOCR executed successfully but found no usable text."}}
        )

    for text, score, poly in zip(texts, scores, polys):
        lines.append(OcrLine(
            text=text,
            confidence=float(score),
            polygon=[
                [float(pt[0]) * scale_x, float(pt[1]) * scale_y]
                for pt in poly
            ]
        ))

    return canonicalize_ocr_lines(lines)
