import logging
from typing import List, Optional
import numpy as np
from fastapi import HTTPException, status
from app.schemas.ocr import OcrLine

logger = logging.getLogger(__name__)

# Initialize PaddleOCR globally to avoid reloading on every request.
# Will be initialized on first use or app startup.
_ocr_model = None

def get_ocr_model():
    global _ocr_model
    if _ocr_model is None:
        try:
            import os
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

def analyze_image(image: np.ndarray) -> List[OcrLine]:
    """
    Runs PaddleOCR on the decoded image and returns structured lines.
    Raises HTTPException with NO_USABLE_TEXT_DETECTED or OCR_PROCESSING_FAILED.
    """
    ocr = get_ocr_model()
    
    try:
        # result is a list of lists: [[[ [x,y],[x,y],[x,y],[x,y] ], ("text", confidence)], ...]
        # Note: result can have multiple lists for multiple text boxes, 
        # usually result[0] contains the actual list of detections.
        result = ocr.ocr(image)
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
            polygon=[[float(pt[0]), float(pt[1])] for pt in poly]
        ))

    return lines
