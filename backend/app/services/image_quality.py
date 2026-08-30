import cv2
import numpy as np
from app.schemas.image_quality import ImageQualityAssessment

# Deterministic Thresholds (Engineering Capture Heuristics)
MIN_SHORT_SIDE = 200
MIN_TOTAL_PIXELS = 100000
MIN_BLUR_SCORE = 100.0  # Lower means more blurry (Variance of Laplacian)
MIN_BRIGHTNESS = 40.0
MAX_BRIGHTNESS = 210.0
MIN_STD_DEV_FOR_DETAIL = 20.0
GLARE_PIXEL_VALUE = 240

def assess_image_quality(image: np.ndarray) -> ImageQualityAssessment:
    """
    Evaluates an OpenCV image array against deterministic quality heuristics.
    Does NOT use ML, LLMs, or cloud services.
    These are engineering capture heuristics only.
    """
    if image is None or image.size == 0:
        raise ValueError("Invalid or empty image array")

    height, width = image.shape[:2]
    
    # Convert to grayscale if it's a color image
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Blur detection using Variance of Laplacian
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

    # Brightness metrics
    brightness = np.mean(gray)
    std_dev = np.std(gray)

    # Glare/Highlight percentage (Diagnostic metric only)
    # White labels naturally have high highlights. This alone does not reject an image.
    glare_pixels = np.sum(gray >= GLARE_PIXEL_VALUE)
    total_pixels = width * height
    glare_percentage = (glare_pixels / total_pixels) * 100.0

    # Assessment logic
    reasons = []
    
    # Resolution Check (supports rectangular crops)
    if min(width, height) < MIN_SHORT_SIDE or total_pixels < MIN_TOTAL_PIXELS:
        reasons.append(f"Image resolution too low ({width}x{height}). Minimum recommended is a {MIN_SHORT_SIDE}px short-side and {MIN_TOTAL_PIXELS} total pixels.")
        
    # Blur Check
    if blur_score < MIN_BLUR_SCORE:
        reasons.append(f"Image appears severely blurry (score: {blur_score:.1f}).")
        
    # Underexposure Check
    if brightness < MIN_BRIGHTNESS:
        reasons.append(f"Image is severely underexposed/too dark (brightness: {brightness:.1f}).")
        
    # Overexposure Check (requires both high brightness and loss of contrast detail)
    if brightness > MAX_BRIGHTNESS and std_dev < MIN_STD_DEV_FOR_DETAIL:
        reasons.append(f"Image is genuinely washed-out/overexposed with lost detail (brightness: {brightness:.1f}, contrast: {std_dev:.1f}).")

    quality_status = "RETAKE_RECOMMENDED" if reasons else "ACCEPTABLE"

    return ImageQualityAssessment(
        width=width,
        height=height,
        blur_score=round(float(blur_score), 2),
        brightness=round(float(brightness), 2),
        glare_percentage=round(float(glare_percentage), 2),
        quality_status=quality_status,
        reasons=reasons
    )
