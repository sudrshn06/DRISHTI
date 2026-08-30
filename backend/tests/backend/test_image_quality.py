import pytest
import cv2
import numpy as np
from app.services.image_quality import assess_image_quality

def create_base_image(width=800, height=800, color=(150, 150, 150), add_text=True):
    """Create a synthetic image, optionally with sharp edges/text."""
    img = np.full((height, width, 3), color, dtype=np.uint8)
    if add_text:
        # Add some sharp shapes so laplacian variance is high and std dev is healthy
        text_color = (0, 0, 0)
        cv2.rectangle(img, (10, 10), (width-10, height-10), text_color, 5)
        cv2.putText(img, "SHARP TEXT", (50, height//2), cv2.FONT_HERSHEY_SIMPLEX, 1.5, text_color, 4)
    return img

def test_sharp_normal_image():
    # 1. sharp normal image -> ACCEPTABLE
    img = create_base_image()
    result = assess_image_quality(img)
    assert result.quality_status == "ACCEPTABLE"
    assert len(result.reasons) == 0

def test_blurred_image():
    # 2. blurred image -> RETAKE_RECOMMENDED
    img = create_base_image()
    # Apply strong Gaussian blur
    blurred = cv2.GaussianBlur(img, (51, 51), 0)
    result = assess_image_quality(blurred)
    assert result.quality_status == "RETAKE_RECOMMENDED"
    assert any("blurry" in r for r in result.reasons)

def test_severely_dark_image():
    # 3. severely dark image -> RETAKE_RECOMMENDED
    img = create_base_image(color=(20, 20, 20), add_text=False)
    # Add some faint text to simulate dark details
    cv2.putText(img, "DARK TEXT", (50, 400), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (30, 30, 30), 4)
    result = assess_image_quality(img)
    assert result.quality_status == "RETAKE_RECOMMENDED"
    assert any("underexposed" in r for r in result.reasons)

def test_washed_out_low_detail_image():
    # 4. genuinely washed-out low-detail image -> RETAKE_RECOMMENDED
    # High brightness, low std dev (no text)
    img = create_base_image(color=(240, 240, 240), add_text=False)
    result = assess_image_quality(img)
    assert result.quality_status == "RETAKE_RECOMMENDED"
    assert any("washed-out" in r for r in result.reasons)

def test_sharp_image_predominantly_white_background():
    # 5. sharp image on predominantly white background -> ACCEPTABLE
    # White background but has sharp dark text giving healthy contrast
    img = create_base_image(color=(255, 255, 255), add_text=True)
    result = assess_image_quality(img)
    assert result.quality_status == "ACCEPTABLE"

def test_sharp_white_label_dark_text():
    # 6. sharp white label with dark text -> ACCEPTABLE
    img = np.full((600, 600, 3), (255, 255, 255), dtype=np.uint8)
    # Add very dense dark text
    for y in range(50, 550, 50):
        cv2.putText(img, "INGREDIENTS: WATER, SUGAR", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    result = assess_image_quality(img)
    assert result.quality_status == "ACCEPTABLE"

def test_useful_rectangular_crop():
    # 7. useful rectangular crop -> ACCEPTABLE
    # E.g. a tall narrow ingredient panel 300x900 (area 270,000, short side 300)
    img = create_base_image(width=300, height=900)
    result = assess_image_quality(img)
    assert result.quality_status == "ACCEPTABLE"

def test_genuinely_tiny_thumbnail():
    # 8. genuinely tiny thumbnail -> RETAKE_RECOMMENDED
    # 150x150
    img = create_base_image(width=150, height=150)
    result = assess_image_quality(img)
    assert result.quality_status == "RETAKE_RECOMMENDED"
    assert any("resolution" in r for r in result.reasons)
