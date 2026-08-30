import cv2
import numpy as np
from typing import List, Optional, Dict, Any, Tuple

def _safe_float(val: Any) -> Optional[float]:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def annotate_evidence_crop(
    image_bytes: bytes,
    field_label: str,
    view_id: str,
    polygons: Optional[List[List[List[float]]]] = None,
    pixel_box: Optional[Dict[str, float]] = None,
    normalized_box: Optional[Dict[str, float]] = None,
    is_clearance: bool = False,
    clearance_box: Optional[Dict[str, float]] = None,
    target_width: int = 600
) -> Optional[bytes]:
    """
    Generates a high-contrast, annotated evidence crop highlighting OCR regions.
    Returns JPEG bytes of the annotated image, or None if image or geometry is unavailable/malformed.
    """
    if not image_bytes:
        return None

    try:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
    except Exception:
        return None

    img_h, img_w = img.shape[:2]
    if img_h <= 0 or img_w <= 0:
        return None

    # Determine bounding coordinates
    x_min, y_min, x_max, y_max = None, None, None, None

    # 1. From pixel_box
    if pixel_box:
        p_xmin = _safe_float(pixel_box.get("x_min"))
        p_ymin = _safe_float(pixel_box.get("y_min"))
        p_xmax = _safe_float(pixel_box.get("x_max"))
        p_ymax = _safe_float(pixel_box.get("y_max"))
        if None not in (p_xmin, p_ymin, p_xmax, p_ymax) and p_xmax > p_xmin and p_ymax > p_ymin:
            x_min, y_min, x_max, y_max = p_xmin, p_ymin, p_xmax, p_ymax

    # 2. From normalized_box
    if x_min is None and normalized_box:
        n_xmin = _safe_float(normalized_box.get("x_min"))
        n_ymin = _safe_float(normalized_box.get("y_min"))
        n_xmax = _safe_float(normalized_box.get("x_max"))
        n_ymax = _safe_float(normalized_box.get("y_max"))
        if None not in (n_xmin, n_ymin, n_xmax, n_ymax) and n_xmax > n_xmin and n_ymax > n_ymin:
            x_min = n_xmin * img_w
            y_min = n_ymin * img_h
            x_max = n_xmax * img_w
            y_max = n_ymax * img_h

    # 3. From polygons
    valid_polys = []
    if polygons:
        for poly in polygons:
            if isinstance(poly, list) and len(poly) >= 3:
                pts = []
                for pt in poly:
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        px = _safe_float(pt[0])
                        py = _safe_float(pt[1])
                        if px is not None and py is not None:
                            # Check if normalized [0.0 - 1.0]
                            if 0.0 <= px <= 1.0 and 0.0 <= py <= 1.0 and img_w > 1 and img_h > 1:
                                px *= img_w
                                py *= img_h
                            pts.append([px, py])
                if len(pts) >= 3:
                    valid_polys.append(np.array(pts, dtype=np.int32))
                    p_arr = np.array(pts)
                    poly_xmin = float(np.min(p_arr[:, 0]))
                    poly_ymin = float(np.min(p_arr[:, 1]))
                    poly_xmax = float(np.max(p_arr[:, 0]))
                    poly_ymax = float(np.max(p_arr[:, 1]))
                    if x_min is None or poly_xmin < x_min:
                        x_min = poly_xmin
                    if y_min is None or poly_ymin < y_min:
                        y_min = poly_ymin
                    if x_max is None or poly_xmax > x_max:
                        x_max = poly_xmax
                    if y_max is None or poly_ymax > y_max:
                        y_max = poly_ymax

    # Fallback if no valid geometry
    if x_min is None or y_min is None or x_max is None or y_max is None:
        return None

    # Clamp coordinates to image boundaries
    x_min = max(0, min(img_w - 1, int(x_min)))
    y_min = max(0, min(img_h - 1, int(y_min)))
    x_max = max(x_min + 1, min(img_w, int(x_max)))
    y_max = max(y_min + 1, min(img_h, int(y_max)))

    # Compute crop window with generous context margin (e.g. 80% box size padding)
    box_w = x_max - x_min
    box_h = y_max - y_min
    pad_x = max(int(box_w * 0.8), 40)
    pad_y = max(int(box_h * 0.8), 30)

    crop_xmin = max(0, x_min - pad_x)
    crop_ymin = max(0, y_min - pad_y)
    crop_xmax = min(img_w, x_max + pad_x)
    crop_ymax = min(img_h, y_max + pad_y)

    cropped = img[crop_ymin:crop_ymax, crop_xmin:crop_xmax].copy()
    overlay = cropped.copy()

    # Draw highlights on overlay (BGR colors)
    # Emerald green #059669 -> BGR (105, 150, 5) or Blue #3B82F6 -> BGR (246, 130, 59)
    fill_color = (246, 130, 59) # Vibrant Blue
    border_color = (200, 80, 20)

    if valid_polys:
        for poly in valid_polys:
            shifted_poly = poly.copy()
            shifted_poly[:, 0] -= crop_xmin
            shifted_poly[:, 1] -= crop_ymin
            cv2.fillPoly(overlay, [shifted_poly], fill_color)
            cv2.polylines(cropped, [shifted_poly], isClosed=True, color=border_color, thickness=2)
    else:
        # Draw bounding rectangle
        bx1 = max(0, x_min - crop_xmin)
        by1 = max(0, y_min - crop_ymin)
        bx2 = min(cropped.shape[1], x_max - crop_xmin)
        by2 = min(cropped.shape[0], y_max - crop_ymin)
        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), fill_color, -1)
        cv2.rectangle(cropped, (bx1, by1), (bx2, by2), border_color, 2)

    # Optional: Clearance Zone for Rule 8
    if is_clearance:
        c_pad_x = box_w * 2 # 2x horizontal
        c_pad_y = box_h * 1 # 1x vertical
        cx1 = max(0, int(x_min - c_pad_x - crop_xmin))
        cy1 = max(0, int(y_min - c_pad_y - crop_ymin))
        cx2 = min(cropped.shape[1], int(x_max + c_pad_x - crop_xmin))
        cy2 = min(cropped.shape[0], int(y_max + c_pad_y - crop_ymin))
        # Amber dashed border representation
        cv2.rectangle(cropped, (cx1, cy1), (cx2, cy2), (6, 119, 217), 1)

    # Alpha blend overlay with cropped image
    alpha = 0.35
    cv2.addWeighted(overlay, alpha, cropped, 1 - alpha, 0, cropped)

    # Add label header pill/badge
    label_text = f"{field_label.replace('_', ' ')} [{view_id}]"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45
    font_thick = 1
    (tw, th), baseline = cv2.getTextSize(label_text, font, font_scale, font_thick)

    bx = max(4, x_min - crop_xmin)
    by = max(th + 6, y_min - crop_ymin - 6)
    cv2.rectangle(cropped, (bx - 2, by - th - 4), (bx + tw + 4, by + baseline), (15, 23, 42), -1)
    cv2.putText(cropped, label_text, (bx, by), font, font_scale, (255, 255, 255), font_thick, cv2.LINE_AA)

    # Resize if wider than target width while preserving aspect ratio
    ch, cw = cropped.shape[:2]
    if cw > target_width:
        ratio = target_width / float(cw)
        new_h = int(ch * ratio)
        cropped = cv2.resize(cropped, (target_width, new_h), interpolation=cv2.INTER_AREA)

    # Encode as JPEG
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 88]
    success, encoded = cv2.imencode('.jpg', cropped, encode_params)
    if not success:
        return None

    return encoded.tobytes()
