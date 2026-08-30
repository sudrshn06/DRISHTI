import sys
import cv2
import json
from app.services.image_quality import assess_image_quality

def print_report(image_path):
    print(f"\nIMAGE: {image_path}")
    image = cv2.imread(image_path)
    if image is None:
        print("Failed to read image")
        return

    result = assess_image_quality(image)
    
    print(f"{result.width} x {result.height}")
    print(f"blur_score: {result.blur_score}")
    print(f"brightness: {result.brightness}")
    print(f"glare/highlight percentage: {result.glare_percentage}")
    
    # Extract underexposed/overexposed purely for reporting, 
    # mirroring the heuristic logic
    MIN_BRIGHTNESS = 40.0
    MAX_BRIGHTNESS = 210.0
    underexposed = result.brightness < MIN_BRIGHTNESS
    overexposed = result.brightness > MAX_BRIGHTNESS
    
    print(f"underexposed: {underexposed}")
    print(f"overexposed: {overexposed}")
    print(f"quality_status: {result.quality_status}")
    print("reasons:")
    for r in result.reasons:
        print(f"  - {r}")

if __name__ == "__main__":
    images = [
        "tests/fixtures/real_world/low_quality_black_bottle.jpg",
        "tests/fixtures/real_world/real_soda_bottle.jpg",
        "tests/fixtures/real_world/pureshield_cleaner.jpg",
        "tests/fixtures/readable_test_label.jpg",
        "tests/fixtures/real_world/coke_can.jpg"
    ]
    for img in images:
        print_report(img)
