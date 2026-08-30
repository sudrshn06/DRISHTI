import hashlib
import threading
from typing import Dict, Optional, Any

_lock = threading.Lock()
_images_by_capture_id: Dict[str, bytes] = {}
_images_by_hash: Dict[str, bytes] = {}
_metadata_by_capture_id: Dict[str, Dict[str, Any]] = {}

def store_capture_image(
    capture_id: str,
    sha256_hash: str,
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    width: Optional[int] = None,
    height: Optional[int] = None
) -> None:
    """
    Temporarily stores capture image bytes and metadata in memory during active inspection sessions.
    When an InspectionReportSnapshot is generated, the required evidence image bytes are embedded
    directly (self-contained) into the snapshot to guarantee report reproducibility across process restarts.
    """
    if not image_bytes:
        return
        
    actual_hash = hashlib.sha256(image_bytes).hexdigest()
    
    with _lock:
        _images_by_capture_id[capture_id] = image_bytes
        _images_by_hash[sha256_hash] = image_bytes
        _images_by_hash[actual_hash] = image_bytes
        _metadata_by_capture_id[capture_id] = {
            "capture_id": capture_id,
            "sha256_hash": sha256_hash,
            "media_type": media_type,
            "width": width,
            "height": height,
            "byte_length": len(image_bytes)
        }

def get_capture_image(capture_id: str) -> Optional[bytes]:
    """Retrieves image bytes by capture ID."""
    with _lock:
        return _images_by_capture_id.get(capture_id)

def get_image_by_hash(sha256_hash: str) -> Optional[bytes]:
    """Retrieves image bytes by original SHA-256 hash."""
    with _lock:
        return _images_by_hash.get(sha256_hash)

def get_image_metadata(capture_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves image metadata for a capture ID."""
    with _lock:
        meta = _metadata_by_capture_id.get(capture_id)
        return dict(meta) if meta else None

def remove_capture_image(capture_id: str) -> None:
    """Removes a capture image and associated metadata from in-memory cache."""
    with _lock:
        _images_by_capture_id.pop(capture_id, None)
        _metadata_by_capture_id.pop(capture_id, None)

def clear_image_store() -> None:
    """Clears the in-memory image store (useful for testing)."""
    with _lock:
        _images_by_capture_id.clear()
        _images_by_hash.clear()
        _metadata_by_capture_id.clear()

