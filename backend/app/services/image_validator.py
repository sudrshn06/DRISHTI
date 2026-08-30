import hashlib
import cv2
import numpy as np
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings

def validate_and_decode_image(file: UploadFile) -> tuple[np.ndarray, str]:
    """
    Validates the uploaded file for:
    - Existence
    - File size <= 10MB
    - Magic bytes signature (JPEG or PNG)
    - Valid image decoding via OpenCV
    - Image dimensions <= 20 MP

    Returns a tuple of (decoded_image, sha256_hash).
    Raises HTTPException on validation failure.
    """
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_FILE_TYPE", "message": "No file uploaded."}}
        )

    # Read bytes
    file_bytes = file.file.read()
    
    # Not empty check
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_IMAGE", "message": "File is empty."}}
        )

    # Size check (10 MB = 10 * 1024 * 1024 bytes)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error": {"code": "IMAGE_TOO_LARGE", "message": f"Image exceeds {settings.max_upload_size_mb} MB limit."}}
        )

    # Magic bytes check for JPEG (FF D8) or PNG (89 50 4E 47)
    is_jpeg = file_bytes.startswith(b'\xff\xd8')
    is_png = file_bytes.startswith(b'\x89PNG\r\n\x1a\n')
    
    if not (is_jpeg or is_png):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"error": {"code": "INVALID_FILE_TYPE", "message": "Only JPEG and PNG images are supported."}}
        )

    # Calculate SHA-256 of original bytes
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    # Decode via OpenCV
    np_array = np.frombuffer(file_bytes, np.uint8)
    decoded_image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

    if decoded_image is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_IMAGE", "message": "The uploaded file could not be decoded as a valid image."}}
        )

    # Dimensions check (<= 20 MP)
    height, width = decoded_image.shape[:2]
    total_pixels = height * width
    max_pixels = 20_000_000

    if total_pixels > max_pixels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "IMAGE_DIMENSIONS_TOO_LARGE", "message": "Image dimensions exceed the 20 megapixel limit."}}
        )

    return decoded_image, sha256_hash
