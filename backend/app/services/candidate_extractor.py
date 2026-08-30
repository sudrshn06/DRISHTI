import re
from typing import List, Dict, Any

from app.schemas.ocr import OcrLine, FieldCandidate, NetQuantityNormalized
from app.services.declaration_normalizer import (
    parse_mrp,
    parse_net_quantity,
    parse_business_declaration,
    parse_date_declaration,
    parse_consumer_care,
    parse_country_of_origin,
    parse_common_generic_name,
    parse_unit_sale_price
)

def extract_candidates(
    lines: List[OcrLine],
    evidence_map: Dict[str, str]
) -> List[FieldCandidate]:
    """
    Deterministically extracts field candidates from OCR lines.
    Evidence map associates line index/text to an evidence_id.
    """
    candidates = {
        "MRP": FieldCandidate(field="MRP", status="NOT_DETECTED"),
        "CONSUMER_CARE": FieldCandidate(
            field="CONSUMER_CARE",
            status="NOT_DETECTED"
        ),
        "UNIT_SALE_PRICE": FieldCandidate(
            field="UNIT_SALE_PRICE",
            status="NOT_DETECTED"
        )
    }
    date_candidates = []
    business_candidates = []
    country_candidates = []
    common_name_candidates = []
    qr_instruction_candidates = []
    brand_candidates = []
    
    collected_nqs: List[Dict[str, Any]] = []
    collected_nq_failures: List[Dict[str, Any]] = []
    
    num_lines = len(lines)
    in_nutrition_context = False

    # Calculate median line height of OCR lines in pixels/units
    heights = []
    for l in lines:
        if l.polygon and len(l.polygon) >= 2:
            ys = [pt[1] for pt in l.polygon if isinstance(pt, (list, tuple)) and len(pt) >= 2]
            if ys:
                h = max(ys) - min(ys)
                if h > 0:
                    heights.append(h)
    median_line_height = float(sum(heights) / len(heights)) if heights else 15.0 # fallback

    def get_line_bbox(l: OcrLine):
        if not l.polygon or len(l.polygon) < 2:
            return 0.0, 0.0, 0.0, 0.0
        xs = [pt[0] for pt in l.polygon if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        ys = [pt[1] for pt in l.polygon if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if not xs or not ys:
            return 0.0, 0.0, 0.0, 0.0
        return min(xs), max(xs), min(ys), max(ys)

    # Lookahead helpers
    def is_barcode_line(line_text: str) -> bool:
        cleaned = line_text.strip().replace(" ", "").replace("-", "")
        if cleaned.isdigit() and len(cleaned) in (8, 12, 13, 14):
            return True
        if re.search(r"\b(?:BARCODE|EAN|UPC|GTIN|FSSAI|LIC\.?\s*NO|LIC\s*NO)\b", line_text.upper()):
            return True
        return False

    def is_declaration_heading(line_text: str) -> bool:
        if is_barcode_line(line_text):
            return True
        t = line_text.upper()
        return (
            "MFG" in t or "MANUFACTURED" in t or "PACKED" in t or "PKD" in t or "MFD" in t
            or "IMPORTER" in t or "IMPORTED" in t or "MARKETED" in t
            or "USE BY" in t or "EXP" in t or "BEST BEFORE" in t or "DATE" in t
            or "NET QTY" in t or "NET WEIGHT" in t or "NET VOL" in t or "NET QUANTITY" in t or "NET WT" in t
            or "MRP" in t or "MAXIMUM RETAIL PRICE" in t
            or "UNIT SALE PRICE" in t or "USP" in t
            or "CONSUMER CARE" in t or "CUSTOMER CARE" in t or "TOLL FREE" in t or "CONTACT" in t
            or "INGREDIENTS" in t or "NUTRITION" in t
            or "LICENSE" in t or "LIC. NO" in t or "LIC NO" in t or "FSSAI" in t
            or "BARCODE" in t
            or "COUNTRY OF ORIGIN" in t or "COUNTRY OF MANUFACTURE" in t or "COUNTRY OF ASSEMBLY" in t
            or "MADE IN" in t
            or bool(re.search(r"^(?:COMMON|GENERIC)\s*NAME\s*:", t)) or bool(re.search(r"^NAME\s*OF\s*(?:THE\s*)?COMMODITY\s*:", t)) or bool(re.search(r"^COMMODITY\s*:", t)) or bool(re.search(r"^PRODUCT\s*NAME\s*:", t))
            or bool(re.search(r"^(?:BRAND|TRADE\s*MARK)\s*:", t)) or bool(re.search(r"\bBRAND\s*NAME\s*:", t))
            or "QR" in t or "SCAN" in t
        )

    consumed_date_indices = set()
    used_line_indices = set()

    for i, line in enumerate(lines):
        if i in used_line_indices:
            continue
        text = line.text.upper()
        evidence_id = evidence_map.get(str(i))
        current_confidence = line.confidence

        def get_lookahead_text(max_lines=3):
            lookahead_text = text
            lookahead_evidence = [evidence_id] if evidence_id else []
            lookahead_confidence = [current_confidence]
            consumed_count = 0
            
            curr_xmin, curr_xmax, curr_ymin, curr_ymax = get_line_bbox(line)
            last_ymax = curr_ymax
            
            for j in range(1, max_lines + 1):
                if i + j < num_lines:
                    next_line = lines[i + j]
                    if is_declaration_heading(next_line.text):
                        break
                    
                    next_xmin, next_xmax, next_ymin, next_ymax = get_line_bbox(next_line)
                    
                    # R4: Prevent Boundary Contamination
                    # 1. Vertical gap
                    if next_ymin - last_ymax > 2.5 * median_line_height:
                        break
                    # 2. Horizontal overlap (column split check)
                    if curr_xmax > curr_xmin and next_xmax > next_xmin:
                        overlap_w = min(curr_xmax, next_xmax) - max(curr_xmin, next_xmin)
                        curr_w = curr_xmax - curr_xmin
                        next_w = next_xmax - next_xmin
                        min_w = min(curr_w, next_w)
                        if min_w > 0 and overlap_w < 0.1 * min_w:
                            break
                    
                    lookahead_text += "\n" + next_line.text
                    next_ev_id = evidence_map.get(str(i + j))
                    if next_ev_id and next_ev_id not in lookahead_evidence:
                        lookahead_evidence.append(next_ev_id)
                    lookahead_confidence.append(next_line.confidence)
                    last_ymax = next_ymax
                    consumed_count = j
            
            avg_conf = sum(lookahead_confidence) / len(lookahead_confidence) if lookahead_confidence else 0
            return lookahead_text, lookahead_evidence, avg_conf, consumed_count

        # --- MRP ---
        if "MRP" in text or "MAXIMUM RETAIL PRICE" in text or "RS" in text or "₹" in text:
            parsed_mrp = parse_mrp(text)
            lookahead_mrp_text = None
            lookahead_mrp_ev = None
            lookahead_mrp_conf = None
            
            if not parsed_mrp and ("MRP" in text or "MAXIMUM RETAIL PRICE" in text or "₹" in text or "RS" in text):
                lookahead_mrp_text, lookahead_mrp_ev, lookahead_mrp_conf, consumed = get_lookahead_text(max_lines=2)
                parsed_mrp = parse_mrp(lookahead_mrp_text)
                if parsed_mrp:
                    for offset in range(1, consumed + 1):
                        used_line_indices.add(i + offset)
                
            if parsed_mrp:
                cand = candidates["MRP"]
                use_conf = lookahead_mrp_conf if (lookahead_mrp_text and lookahead_mrp_conf is not None) else current_confidence
                use_raw = lookahead_mrp_text if lookahead_mrp_text else line.text
                use_ev = lookahead_mrp_ev if lookahead_mrp_ev else ([evidence_id] if evidence_id else [])
                cand.status = "DETECTED" if use_conf >= 0.8 else "REVIEW_REQUIRED"
                cand.normalized_value = parsed_mrp
                cand.raw_value = use_raw
                cand.confidence = use_conf
                for ev in use_ev:
                    if ev not in cand.evidence_ids:
                        cand.evidence_ids.append(ev)
            elif ("MRP" in text or "MAXIMUM RETAIL PRICE" in text) and candidates["MRP"].status == "NOT_DETECTED":
                # Keyword detected but value couldn't be parsed
                cand = candidates["MRP"]
                cand.status = "REVIEW_REQUIRED"
                cand.raw_value = line.text
                cand.confidence = current_confidence
                if evidence_id and evidence_id not in cand.evidence_ids:
                    cand.evidence_ids.append(evidence_id)

        # --- UNIT SALE PRICE ---
        # Look for explicit USP text or price/unit formats like Rs 10/kg
        if (
            "UNIT SALE PRICE" in text or "USP" in text
            or re.search(r"(?:RS\.?|₹|INR)?\s*\d+(?:\.\d{1,2})?\s*(?:/|PER)\s*(?:\d+(?:\.\d+)?)?\s*(?:G|GM|GRAM|KG|KILOGRAM|ML|MILLILITRE|L|LITRE|CM|CENTIMETRE|M|METRE|UNIT|NUMBER)\b", text)
        ):
            parsed_usp = parse_unit_sale_price(text)
            if parsed_usp:
                # Disambiguate: don't extract as USP if it's explicitly labeled MRP and lacks USP labels
                is_explicit_mrp = "MRP" in text or "MAXIMUM RETAIL PRICE" in text
                is_explicit_usp = "UNIT SALE PRICE" in text or "USP" in text
                
                if is_explicit_mrp and not is_explicit_usp:
                    # Likely not a USP, but an oddly formatted MRP
                    pass
                else:
                    cand = FieldCandidate(
                        field="UNIT_SALE_PRICE",
                        status="DETECTED" if current_confidence >= 0.8 else "REVIEW_REQUIRED",
                        normalized_value=parsed_usp,
                        raw_value=line.text,
                        confidence=current_confidence,
                        evidence_ids=[evidence_id] if evidence_id else []
                    )
                    candidates.setdefault("UNIT_SALE_PRICE", cand)
                    if cand not in candidates.values() and isinstance(candidates.get("UNIT_SALE_PRICE"), list):
                        # This shouldn't happen based on how candidates dict is used, but to be safe:
                        pass
                    elif "UNIT_SALE_PRICE" in candidates and candidates["UNIT_SALE_PRICE"].status != "DETECTED":
                        candidates["UNIT_SALE_PRICE"] = cand
            elif "UNIT SALE PRICE" in text or "USP" in text:
                if "UNIT_SALE_PRICE" not in candidates or candidates["UNIT_SALE_PRICE"].status == "NOT_DETECTED":
                    cand = FieldCandidate(
                        field="UNIT_SALE_PRICE",
                        status="REVIEW_REQUIRED",
                        raw_value=line.text,
                        confidence=current_confidence,
                        evidence_ids=[evidence_id] if evidence_id else []
                    )
                    candidates["UNIT_SALE_PRICE"] = cand

        # --- NET QUANTITY ---
        is_explicit_nq = (
            "NET QTY" in text
            or "NET QUANTITY" in text
            or "NET WEIGHT" in text
            or "NET WT" in text
            or "NET VOL" in text
        )
        
        # Context tracking
        if any(k in text for k in ["NUTRITION", "NUTRITIONAL", "NUTRIMENTS", "NUTRITIVE"]):
            in_nutrition_context = True
        elif is_explicit_nq or "MANUFACTURED" in text or "PACKED" in text or "MARKETED" in text or "INGREDIENTS" in text:
            in_nutrition_context = False

        is_standalone_quantity = bool(re.search(r"\b\d+(?:\.\d+)?\s*(G|KG|ML|L)\b", text))
        has_nutrition_words = any(k in text for k in ["PROTEIN", "FAT", "SODIUM", "CARBOHYDRATE", "SUGAR", "ENERGY", "KCAL", "CHOLESTEROL", "VITAMIN", "DIETARY"])

        if is_explicit_nq or (is_standalone_quantity and not in_nutrition_context and not has_nutrition_words):
            lookahead_text, lookahead_ev, lookahead_conf, consumed = get_lookahead_text(max_lines=1)
            
            parsed_nq = parse_net_quantity(text)
            parsed_lookahead = parse_net_quantity(lookahead_text)
            
            if not parsed_nq and parsed_lookahead:
                parsed_nq = parsed_lookahead
                text_to_use = lookahead_text
                ev_to_use = lookahead_ev
                conf_to_use = lookahead_conf
                for offset in range(1, consumed + 1):
                    used_line_indices.add(i + offset)
            else:
                text_to_use = text
                ev_to_use = [evidence_id] if evidence_id else []
                conf_to_use = current_confidence

            if parsed_nq:
                collected_nqs.append({
                    "is_anchored": is_explicit_nq,
                    "parsed": parsed_nq,
                    "text": text_to_use,
                    "evidence_ids": ev_to_use,
                    "confidence": conf_to_use
                })
            elif "NET" in text:
                collected_nq_failures.append({
                    "text": line.text,
                    "evidence_ids": [evidence_id] if evidence_id else [],
                    "confidence": current_confidence
                })

        # --- MANUFACTURER / PACKER / IMPORTER ---
        if (
            "MFG" in text
            or "MANUFACTURED" in text
            or "PACKED" in text
            or "IMPORTER" in text
            or "IMPORTED" in text
            or "MARKETED" in text
            or "MFD" in text
            or "PKD" in text
        ):
            lookahead_text, lookahead_ev, lookahead_conf, consumed = get_lookahead_text(max_lines=5)
            parsed_current = parse_business_declaration(text)
            parsed_business = parse_business_declaration(lookahead_text)
            
            if parsed_business and parsed_business.name:
                cand = FieldCandidate(
                    field="MANUFACTURER_PACKER_IMPORTER",
                    status="DETECTED" if lookahead_conf >= 0.8 else "REVIEW_REQUIRED",
                    normalized_value=parsed_business,
                    raw_value=lookahead_text,
                    confidence=lookahead_conf,
                    evidence_ids=lookahead_ev
                )
                business_candidates.append(cand)
                for offset in range(1, consumed + 1):
                    used_line_indices.add(i + offset)
            elif parsed_current and parsed_current.name:
                cand = FieldCandidate(
                    field="MANUFACTURER_PACKER_IMPORTER",
                    status="DETECTED" if current_confidence >= 0.8 else "REVIEW_REQUIRED",
                    normalized_value=parsed_current,
                    raw_value=text,
                    confidence=current_confidence,
                    evidence_ids=[evidence_id] if evidence_id else []
                )
                business_candidates.append(cand)
            elif parsed_business:
                cand = FieldCandidate(
                    field="MANUFACTURER_PACKER_IMPORTER",
                    status="REVIEW_REQUIRED",
                    normalized_value=parsed_business,
                    raw_value=text,
                    confidence=current_confidence,
                    evidence_ids=[evidence_id] if evidence_id else []
                )
                business_candidates.append(cand)
            elif not business_candidates and (" BY" in text or "IMPORTER" in text or "MARKETED" in text):
                cand = FieldCandidate(
                    field="MANUFACTURER_PACKER_IMPORTER",
                    status="REVIEW_REQUIRED",
                    raw_value=text,
                    confidence=current_confidence,
                    evidence_ids=[evidence_id] if evidence_id else []
                )
                business_candidates.append(cand)

        # --- MONTH / YEAR ---
        if i not in consumed_date_indices and (
            "PKD" in text
            or "MFD" in text
            or "MFG" in text
            or "DATE" in text
            or "USE BY" in text
            or "EXP" in text
            or "BEST BEFORE" in text
            or "IMPORTED" in text
            or "IMPORT DATE" in text
            or re.search(r"\b(0[1-9]|1[0-2])[-/](20\d{2})\b", text)
            or re.search(r"\b20[2-3][0-9]\b", text)
        ):
            parsed_current = parse_date_declaration(text)
            if parsed_current:
                cand = FieldCandidate(
                    field="MONTH_YEAR",
                    status="DETECTED" if current_confidence >= 0.8 else "REVIEW_REQUIRED",
                    normalized_value=parsed_current,
                    raw_value=line.text,
                    confidence=current_confidence,
                    evidence_ids=[evidence_id] if evidence_id else []
                )
                date_candidates.append(cand)
            else:
                # Sometimes dates are split over lines, e.g. "Best Before\n12 Months" or "MFD\n12/2023"
                lookahead_text, lookahead_ev, lookahead_conf, consumed = get_lookahead_text(max_lines=1)
                parsed_date = parse_date_declaration(lookahead_text)
                
                if parsed_date:
                    consumed_date_indices.add(i + 1)
                    for offset in range(1, consumed + 1):
                        used_line_indices.add(i + offset)
                    cand = FieldCandidate(
                        field="MONTH_YEAR",
                        status="DETECTED" if lookahead_conf >= 0.8 else "REVIEW_REQUIRED",
                        normalized_value=parsed_date,
                        raw_value=lookahead_text,
                        confidence=lookahead_conf,
                        evidence_ids=lookahead_ev
                    )
                    date_candidates.append(cand)
                elif ("DATE" in text or "EXP" in text or "MFG" in text or "PKD" in text or "MFD" in text or "USE BY" in text or "BEST BEFORE" in text):
                    # Disambiguate from business declarations like "MFD. BY"
                    is_business_prefix = bool(re.search(r"\b(?:MFG|MFD|PKD|MANUFACTURED|PACKED)\b\.?\s*(?:&.*?)?\s*BY\b", text))
                    if not is_business_prefix:
                        cand = FieldCandidate(
                            field="MONTH_YEAR",
                            status="REVIEW_REQUIRED",
                            raw_value=line.text,
                            confidence=current_confidence,
                            evidence_ids=[evidence_id] if evidence_id else []
                        )
                        date_candidates.append(cand)

        # --- COUNTRY OF ORIGIN ---
        if (
            "COUNTRY OF ORIGIN" in text
            or "COUNTRY OF MANUFACTURE" in text
            or "COUNTRY OF ASSEMBLY" in text
            or "MADE IN" in text
        ):
            lookahead_text, lookahead_ev, lookahead_conf, consumed = get_lookahead_text(max_lines=1)
            parsed_country = parse_country_of_origin(lookahead_text)
            
            if parsed_country:
                cand = FieldCandidate(
                    field="COUNTRY_OF_ORIGIN",
                    status="DETECTED" if lookahead_conf >= 0.8 else "REVIEW_REQUIRED",
                    normalized_value=parsed_country,
                    raw_value=lookahead_text,
                    confidence=lookahead_conf,
                    evidence_ids=lookahead_ev
                )
                country_candidates.append(cand)
                for offset in range(1, consumed + 1):
                    used_line_indices.add(i + offset)
            else:
                cand = FieldCandidate(
                    field="COUNTRY_OF_ORIGIN",
                    status="REVIEW_REQUIRED",
                    raw_value=line.text,
                    confidence=current_confidence,
                    evidence_ids=[evidence_id] if evidence_id else []
                )
                country_candidates.append(cand)

        # --- COMMON / GENERIC NAME ---
        is_cgn_trigger = (
            "COMMON NAME" in text
            or "GENERIC NAME" in text
            or "NAME OF COMMODITY" in text
            or "COMMODITY" in text
            or "PRODUCT NAME" in text
            or bool(re.search(r"\b(?:PRODUCT|ITEM|ARTICLE)\s*:\s*", text))
        )
        if is_cgn_trigger:
            parsed_single = parse_common_generic_name(line.text)
            if parsed_single and len(parsed_single.name_text.strip()) >= 2:
                cand = FieldCandidate(
                    field="COMMON_GENERIC_NAME",
                    status="DETECTED" if current_confidence >= 0.8 else "REVIEW_REQUIRED",
                    normalized_value=parsed_single,
                    raw_value=line.text,
                    confidence=current_confidence,
                    evidence_ids=[evidence_id] if evidence_id else []
                )
                common_name_candidates.append(cand)
            else:
                lookahead_text, lookahead_ev, lookahead_conf, consumed = get_lookahead_text(max_lines=1)
                parsed_cgn = parse_common_generic_name(lookahead_text)
                
                if parsed_cgn:
                    cand = FieldCandidate(
                        field="COMMON_GENERIC_NAME",
                        status="DETECTED" if lookahead_conf >= 0.8 else "REVIEW_REQUIRED",
                        normalized_value=parsed_cgn,
                        raw_value=lookahead_text,
                        confidence=lookahead_conf,
                        evidence_ids=lookahead_ev
                    )
                    common_name_candidates.append(cand)
                    for offset in range(1, consumed + 1):
                        used_line_indices.add(i + offset)
                else:
                    cand = FieldCandidate(
                        field="COMMON_GENERIC_NAME",
                        status="REVIEW_REQUIRED",
                        raw_value=line.text,
                        confidence=current_confidence,
                        evidence_ids=[evidence_id] if evidence_id else []
                    )
                    common_name_candidates.append(cand)

        # --- QR INSTRUCTION ---
        if "QR" in text or "SCAN" in text:
            if re.search(r"SCAN\s+QR\s*(?:CODE)?\s*FOR\s*(?:COMMON|GENERIC|COMMODITY|PRODUCT\s*NAME)", text, re.IGNORECASE):
                cand = FieldCandidate(
                    field="COMMON_NAME_QR_INSTRUCTION",
                    status="DETECTED" if current_confidence >= 0.8 else "REVIEW_REQUIRED",
                    raw_value=line.text,
                    confidence=current_confidence,
                    evidence_ids=[evidence_id] if evidence_id else []
                )
                qr_instruction_candidates.append(cand)
            # Not adding NOT_DETECTED logic for every single QR or SCAN text to avoid noise.

        # --- BRAND / TRADE NAME (Informational) ---
        if "®" in line.text or "™" in line.text or re.search(r"\b(?:BRAND|TRADE\s*MARK)\b", text):
            brand_clean = re.sub(r"(?i)\b(?:brand|trade\s*mark)\s*:\s*", "", line.text).strip()
            if brand_clean:
                cand = FieldCandidate(
                    field="BRAND_NAME",
                    status="DETECTED" if current_confidence >= 0.8 else "REVIEW_REQUIRED",
                    raw_value=brand_clean,
                    confidence=current_confidence,
                    evidence_ids=[evidence_id] if evidence_id else []
                )
                brand_candidates.append(cand)

        # --- CONSUMER CARE ---
        is_consumer_care_trigger = (
            "CONSUMER CARE" in text
            or "CUSTOMER CARE" in text
            or "CUSTOMER SUPPORT" in text
            or "SUPPORT@" in text
            or "CUSTOMERSUPPORT" in text
            or "TOLL FREE" in text
            or "HELPLINE" in text
            or "EMAIL" in text
            or "CARE@" in text
            or "FEEDBACK" in text
            or "GRIEVANCE" in text
            or bool(re.search(r"\b(?:PH|PHONE|TEL|TELEPHONE|CONTACT)\b", text))
            or bool(re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", text))
            or bool(re.search(r"(?:1800[-\s]?\d{3,4}[-\s]?\d{3,4})|(?:\+91[-\s]?\d{5}[-\s]?\d{5})", text))
        )
        if is_consumer_care_trigger:
            def is_contact_related(line_text):
                t = line_text.upper()
                if re.search(r"\b(?:CONSUMER|CARE|SUPPORT|CONTACT|ADDRESS|TOLL FREE|EMAIL|CALL|FEEDBACK|WEBSITE|WWW|HTTP|TEL|PHONE|PH|HELPLINE|QUERIES|GRIEVANCE|EXECUTIVE|OFFICER)\b", t):
                    return True
                if re.search(r"\b(?:PIN|FLOOR|BUILDING|ESTATE|NAGAR|MARG|STREET|ROAD|PHASE|PLOT|SECTOR|GIDC|INDUSTRIAL|INDIA|LTD|PVT|LIMITED)\b", t):
                    return True
                if re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", t):
                    return True
                if re.search(r"(?:1800[-\s]?\d{3,4}[-\s]?\d{3,4})|(?:\+91[-\s]?\d{5}[-\s]?\d{5})|(?:\b0\d{2,4}[-\s]?\d{6,8}\b)|(?:\b\d{10}\b)", t):
                    return True
                if re.search(r"\b\d{6}\b", t):
                    return True
                return False

            lookahead_text = text
            lookahead_ev = [evidence_id] if evidence_id else []
            lookahead_conf = [current_confidence]
            
            for j in range(1, 4):
                if i + j < num_lines:
                    next_line = lines[i + j]
                    if is_declaration_heading(next_line.text) or not is_contact_related(next_line.text):
                        break
                    lookahead_text += " " + next_line.text
                    next_ev_id = evidence_map.get(str(i + j))
                    if next_ev_id and next_ev_id not in lookahead_ev:
                        lookahead_ev.append(next_ev_id)
                    lookahead_conf.append(next_line.confidence)
            
            avg_conf = sum(lookahead_conf) / len(lookahead_conf) if lookahead_conf else 0
            parsed_cc = parse_consumer_care(lookahead_text)
            
            if parsed_cc:
                cand = candidates["CONSUMER_CARE"]
                # Merge if existing subfield was already detected
                if cand.normalized_value and hasattr(cand.normalized_value, "email") and hasattr(cand.normalized_value, "phone"):
                    from app.schemas.ocr import ConsumerCareNormalized
                    merged_email = parsed_cc.email or cand.normalized_value.email
                    merged_phone = parsed_cc.phone or cand.normalized_value.phone
                    parsed_cc = ConsumerCareNormalized(email=merged_email, phone=merged_phone)
                
                cand.status = "DETECTED" if avg_conf >= 0.8 else "REVIEW_REQUIRED"
                cand.normalized_value = parsed_cc
                cand.raw_value = lookahead_text
                cand.confidence = avg_conf
                for ev in lookahead_ev:
                    if ev not in cand.evidence_ids:
                        cand.evidence_ids.append(ev)
            elif candidates["CONSUMER_CARE"].status == "NOT_DETECTED" and ("CONSUMER CARE" in text or "TOLL FREE" in text or "CUSTOMER CARE" in text or "HELPLINE" in text or "CONTACT" in text):
                cand = candidates["CONSUMER_CARE"]
                cand.status = "REVIEW_REQUIRED"
                cand.raw_value = line.text
                cand.confidence = current_confidence
                if evidence_id and evidence_id not in cand.evidence_ids:
                    cand.evidence_ids.append(evidence_id)

    final_candidates = list(candidates.values())
    
    # Process collected NET_QUANTITY candidates
    anchored_nqs = [nq for nq in collected_nqs if nq["is_anchored"]]
    standalone_nqs = [nq for nq in collected_nqs if not nq["is_anchored"]]
    
    if anchored_nqs:
        # Check for conflicts
        first_parsed = anchored_nqs[0]["parsed"]
        has_conflict = False
        
        if isinstance(first_parsed, NetQuantityNormalized):
            first_val = first_parsed.model_dump()
            for nq in anchored_nqs[1:]:
                parsed = nq["parsed"]
                if isinstance(parsed, NetQuantityNormalized) and parsed.model_dump() != first_val:
                    has_conflict = True
                    break
        
        if has_conflict:
            conflict_ev_ids: List[str] = []
            for nq in anchored_nqs:
                for ev in nq["evidence_ids"]:
                    if isinstance(ev, str) and ev not in conflict_ev_ids:
                        conflict_ev_ids.append(ev)
                        
            final_candidates.append(FieldCandidate(
                field="NET_QUANTITY",
                status="REVIEW_REQUIRED",
                raw_value="Multiple conflicting anchored declarations",
                evidence_ids=conflict_ev_ids
            ))
        else:
            nq = anchored_nqs[0]
            nq_ev_ids: List[str] = [str(ev) for ev in nq["evidence_ids"]]
            final_candidates.append(FieldCandidate(
                field="NET_QUANTITY",
                status="DETECTED" if float(nq["confidence"]) >= 0.8 else "REVIEW_REQUIRED",
                normalized_value=nq["parsed"],
                raw_value=str(nq["text"]),
                confidence=float(nq["confidence"]),
                evidence_ids=nq_ev_ids
            ))
    elif standalone_nqs:
        # Standalone evidence without context must NOT automatically become DETECTED
        nq = standalone_nqs[0]
        nq_ev_ids: List[str] = [str(ev) for ev in nq["evidence_ids"]]
        final_candidates.append(FieldCandidate(
            field="NET_QUANTITY",
            status="REVIEW_REQUIRED",
            normalized_value=nq["parsed"],
            raw_value=str(nq["text"]),
            confidence=float(nq["confidence"]),
            evidence_ids=nq_ev_ids
        ))
    elif collected_nq_failures:
        # Keyword detected but value couldn't be parsed
        fail = collected_nq_failures[0]
        final_candidates.append(FieldCandidate(
            field="NET_QUANTITY",
            status="REVIEW_REQUIRED",
            raw_value=fail["text"],
            confidence=fail["confidence"],
            evidence_ids=fail["evidence_ids"]
        ))
    else:
        final_candidates.append(FieldCandidate(
            field="NET_QUANTITY",
            status="NOT_DETECTED"
        ))
        
    if date_candidates:
        strong_dates = []
        for cand in date_candidates:
            if cand.normalized_value and getattr(cand.normalized_value, "type", "UNKNOWN") != "UNKNOWN":
                strong_dates.append(cand)
                
        dedup_dates = []
        for cand in date_candidates:
            if cand.normalized_value and getattr(cand.normalized_value, "type", "UNKNOWN") == "UNKNOWN":
                is_redundant = False
                for strong_cand in strong_dates:
                    ev_overlap = any(ev in strong_cand.evidence_ids for ev in cand.evidence_ids)
                    if ev_overlap:
                        val_u = cand.normalized_value
                        val_s = strong_cand.normalized_value
                        if val_u.month == val_s.month and val_u.year == val_s.year and val_u.day == val_s.day:
                            is_redundant = True
                            break
                if is_redundant:
                    continue
            dedup_dates.append(cand)
        final_candidates.extend(dedup_dates)
    else:
        final_candidates.append(FieldCandidate(field="MONTH_YEAR", status="NOT_DETECTED"))
        
    if business_candidates:
        final_candidates.extend(business_candidates)
    else:
        final_candidates.append(FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="NOT_DETECTED"))
        
    if country_candidates:
        final_candidates.extend(country_candidates)
    else:
        final_candidates.append(FieldCandidate(field="COUNTRY_OF_ORIGIN", status="NOT_DETECTED"))
        
    if common_name_candidates:
        final_candidates.extend(common_name_candidates)
    else:
        final_candidates.append(FieldCandidate(field="COMMON_GENERIC_NAME", status="NOT_DETECTED"))

    if qr_instruction_candidates:
        final_candidates.extend(qr_instruction_candidates)
    else:
        final_candidates.append(FieldCandidate(field="COMMON_NAME_QR_INSTRUCTION", status="NOT_DETECTED"))

    if brand_candidates:
        final_candidates.extend(brand_candidates)
    else:
        final_candidates.append(FieldCandidate(field="BRAND_NAME", status="NOT_DETECTED"))

    # Generic extraction for BRAND_NAME and COMMON_GENERIC_NAME (R1 & R2)
    # Collect all indices of lines already used for other fields
    def is_unsuitable_for_generic(t: str) -> bool:
        t_upper = t.upper()
        words = [
            "STORE", "KEEP", "PLACE", "DRY", "COOL", "REFRIGERATED", "SUNLIGHT", "HYGIENIC", "AIRTIGHT",
            "NUTRITION", "INGREDIENTS", "CONTAINS", "ALLERGEN", "MAY CONTAIN",
            "MANUFACTURED", "MARKETED", "PACKED", "CONSUMER", "CUSTOMER", "CARE", "FEEDBACK", "TOLL", "FREE", "EMAIL", "WEBSITE", "ADDRESS",
            "BATCH", "LOT", "MFD", "PKD", "EXP", "USE BY", "BEST BEFORE", "DATE", "LIC", "FSSAI", "BARCODE",
            "PRODUCT OF", "MADE IN", "ORIGIN", "COUNTRY", "REGD", "OFFICE", "MARK", "TRADE"
        ]
        if any(w in t_upper for w in words):
            return True
        if len(t) < 3 or len(t) > 40:
            return True
        if sum(c.isdigit() for c in t) > 3:
            return True
        return False

    unclaimed_lines_info = []
    for idx in range(num_lines):
        if idx in used_line_indices:
            continue
        line = lines[idx]
        text_strip = line.text.strip()
        if len(text_strip) < 2 or is_unsuitable_for_generic(text_strip):
            continue
        if is_barcode_line(text_strip) or is_declaration_heading(text_strip):
            continue
        if re.search(r"\b(?:RS\.?|₹|INR|\d+(?:\.\d+)?\s*(?:G|KG|ML|L))\b", text_strip.upper()):
            continue
            
        xmin, xmax, ymin, ymax = get_line_bbox(line)
        h = ymax - ymin
        y_center = (ymin + ymax) / 2
        h_ratio = h / median_line_height if median_line_height > 0 else 1.0
        
        unclaimed_lines_info.append({
            "index": idx,
            "line": line,
            "text": text_strip,
            "height": h,
            "height_ratio": h_ratio,
            "y_center": y_center,
            "ymin": ymin,
            "evidence_id": evidence_map.get(str(idx))
        })

    if unclaimed_lines_info:
        unclaimed_sorted = sorted(unclaimed_lines_info, key=lambda x: x["ymin"])
        best_brand = None
        best_brand_score = -999.0
        best_product = None
        best_product_score = -999.0
        
        max_ymin = max((x["ymin"] for x in unclaimed_lines_info), default=1.0)
        
        for info in unclaimed_sorted:
            rel_ymin = info["ymin"] / max_ymin if max_ymin > 0 else 0.0
            brand_score = info["height_ratio"] * 3.0 - rel_ymin * 5.0
            pos_penalty = abs(rel_ymin - 0.35) * 4.0
            product_score = info["height_ratio"] * 2.5 - pos_penalty
            
            if brand_score > best_brand_score and rel_ymin < 0.5:
                best_brand_score = brand_score
                best_brand = info
                
            if product_score > best_product_score and rel_ymin < 0.7:
                best_product_score = product_score
                best_product = info
                
        if best_brand and best_product and best_brand["index"] == best_product["index"]:
            if len(unclaimed_lines_info) > 1:
                # Re-evaluate product candidate excluding the brand candidate
                next_best_product = None
                next_best_score = -999.0
                for info in unclaimed_sorted:
                    if info["index"] == best_brand["index"]:
                        continue
                    rel_ymin = info["ymin"] / max_ymin if max_ymin > 0 else 0.0
                    pos_penalty = abs(rel_ymin - 0.35) * 4.0
                    product_score = info["height_ratio"] * 2.5 - pos_penalty
                    if product_score > next_best_score and rel_ymin < 0.7:
                        next_best_score = product_score
                        next_best_product = info
                best_product = next_best_product
            else:
                best_product = None
                
        has_detected_brand = any(c.field == "BRAND_NAME" and c.status == "DETECTED" for c in final_candidates)
        has_detected_cgn = any(c.field == "COMMON_GENERIC_NAME" and c.status == "DETECTED" for c in final_candidates)
        
        if not has_detected_brand and best_brand:
            brand_cand = FieldCandidate(
                field="BRAND_NAME",
                status="REVIEW_REQUIRED",
                raw_value=best_brand["text"],
                confidence=best_brand["line"].confidence,
                evidence_ids=[best_brand["evidence_id"]] if best_brand["evidence_id"] else []
            )
            existing_brand = next((c for c in final_candidates if c.field == "BRAND_NAME"), None)
            if existing_brand:
                if existing_brand.status == "NOT_DETECTED":
                    existing_brand.status = "REVIEW_REQUIRED"
                    existing_brand.raw_value = brand_cand.raw_value
                    existing_brand.confidence = brand_cand.confidence
                    existing_brand.evidence_ids = brand_cand.evidence_ids
            else:
                final_candidates.append(brand_cand)
                
        if not has_detected_cgn and best_product:
            from app.schemas.ocr import CommonGenericNameNormalized
            product_cand = FieldCandidate(
                field="COMMON_GENERIC_NAME",
                status="REVIEW_REQUIRED",
                raw_value=best_product["text"],
                normalized_value=CommonGenericNameNormalized(name_text=best_product["text"]),
                confidence=best_product["line"].confidence,
                evidence_ids=[best_product["evidence_id"]] if best_product["evidence_id"] else []
            )
            existing_cgn = next((c for c in final_candidates if c.field == "COMMON_GENERIC_NAME"), None)
            if existing_cgn:
                if existing_cgn.status == "NOT_DETECTED":
                    existing_cgn.status = "REVIEW_REQUIRED"
                    existing_cgn.raw_value = product_cand.raw_value
                    existing_cgn.normalized_value = product_cand.normalized_value
                    existing_cgn.confidence = product_cand.confidence
                    existing_cgn.evidence_ids = product_cand.evidence_ids
            else:
                final_candidates.append(product_cand)
        
    # ----------------------------------------------------
    # FSSAI / Food Label candidate extraction (Phase 10C)
    # ----------------------------------------------------
    fssai_lic = None
    veg_nonveg = None
    ingredients_statement = None
    ingredients_tokens = []
    allergen_statement = None
    nutrition_detected = False
    nut_text_lines = []
    
    lic_evidence_ids = []
    veg_evidence_ids = []
    ing_evidence_ids = []
    all_evidence_ids = []
    nut_evidence_ids = []
    
    lic_capture_ids = []
    veg_capture_ids = []
    ing_capture_ids = []
    all_capture_ids = []
    nut_capture_ids = []

    for idx, line in enumerate(lines):
        line_text = line.text.strip()
        line_text_upper = line_text.upper()
        ev_id = evidence_map.get(str(idx))
        
        # 1. Licence number (14 digits starting with 1 or 2, allowing optional spaces/hyphens)
        clean_lic_digits = re.sub(r"[^\d]", "", line_text)
        if lic_match := re.search(r"\b([12]\d{13})\b", clean_lic_digits):
            fssai_lic = lic_match.group(1)
            if ev_id and ev_id not in lic_evidence_ids:
                lic_evidence_ids.append(ev_id)
        elif any(k in line_text_upper for k in ["FSSAI", "LIC NO", "LIC. NO", "LICENCE NO", "LICENSE NO"]):
            # Check lookahead on next line if anchor is standalone
            if idx + 1 < len(lines):
                next_clean = re.sub(r"[^\d]", "", lines[idx + 1].text)
                if next_match := re.search(r"\b([12]\d{13})\b", next_clean):
                    fssai_lic = next_match.group(1)
                    if ev_id and ev_id not in lic_evidence_ids:
                        lic_evidence_ids.append(ev_id)
                    next_ev = evidence_map.get(str(idx + 1))
                    if next_ev and next_ev not in lic_evidence_ids:
                        lic_evidence_ids.append(next_ev)

        # 2. Veg / Non Veg
        if veg_match := re.search(r"\b(100%\s*VEGETARIAN|100%\s*VEG|PURE\s*VEGETARIAN|PURE\s*VEG|VEGETARIAN|NON[- ]VEGETARIAN|VEG|NON[- ]VEG|GREEN\s*DOT|BROWN\s*DOT|BROWN\s*TRIANGLE|GREEN\s*CIRCLE)\b", line_text_upper):
            veg_nonveg = veg_match.group(1)
            if ev_id and ev_id not in veg_evidence_ids:
                veg_evidence_ids.append(ev_id)
                
        # 3. Ingredients
        if "INGREDIENT" in line_text_upper and not ingredients_statement:
            ing_text_parts = [line_text]
            if ev_id:
                ing_evidence_ids.append(ev_id)
            for j in range(1, 8):
                if idx + j < len(lines):
                    next_l = lines[idx + j]
                    if is_declaration_heading(next_l.text):
                        break
                    ing_text_parts.append(next_l.text.strip())
                    next_ev = evidence_map.get(str(idx + j))
                    if next_ev and next_ev not in ing_evidence_ids:
                        ing_evidence_ids.append(next_ev)
            
            full_ing_text = " ".join(ing_text_parts)
            ingredients_statement = full_ing_text
            clean_text = re.sub(r"(?i)^ingredients\s*:\s*", "", full_ing_text)
            tokens = [t.strip() for t in re.split(r"[,;.]", clean_text) if t.strip()]
            if tokens:
                ingredients_tokens.extend(tokens)

        # 4. Allergen warning
        if any(keyword in line_text_upper for keyword in ["CONTAINS WHEAT", "CONTAINS MILK", "ALLERGEN", "ALLERGY ADVICE", "MAY CONTAIN"]) and not allergen_statement:
            all_text_parts = [line_text]
            if ev_id:
                all_evidence_ids.append(ev_id)
            for j in range(1, 4):
                if idx + j < len(lines):
                    next_l = lines[idx + j]
                    if is_declaration_heading(next_l.text):
                        break
                    all_text_parts.append(next_l.text.strip())
                    next_ev = evidence_map.get(str(idx + j))
                    if next_ev and next_ev not in all_evidence_ids:
                        all_evidence_ids.append(next_ev)
            allergen_statement = " ".join(all_text_parts)

        # 5. Nutrition declaration
        if any(keyword in line_text_upper for keyword in ["NUTRITION", "NUTRITIONAL", "ENERGY", "PROTEIN", "CARBOHYDRATE", "FAT", "SATURATED FAT", "TRANS FAT", "SODIUM", "ADDED SUGAR", "TOTAL SUGAR"]):
            nutrition_detected = True
            nut_text_lines.append(line_text)
            if ev_id and ev_id not in nut_evidence_ids:
                nut_evidence_ids.append(ev_id)

    # Append FSSAI candidates
    if fssai_lic:
        final_candidates.append(FieldCandidate(
            field="FSSAI_LICENCE",
            status="DETECTED",
            raw_value=fssai_lic,
            evidence_ids=lic_evidence_ids,
            capture_ids=lic_capture_ids
        ))
    else:
        final_candidates.append(FieldCandidate(field="FSSAI_LICENCE", status="NOT_DETECTED"))

    if veg_nonveg:
        final_candidates.append(FieldCandidate(
            field="FSSAI_VEG_NONVEG",
            status="DETECTED",
            raw_value=veg_nonveg,
            evidence_ids=veg_evidence_ids,
            capture_ids=veg_capture_ids
        ))
    else:
        final_candidates.append(FieldCandidate(field="FSSAI_VEG_NONVEG", status="NOT_DETECTED"))

    if ingredients_statement:
        final_candidates.append(FieldCandidate(
            field="FSSAI_INGREDIENTS",
            status="DETECTED",
            raw_value=ingredients_statement,
            normalized_value="; ".join(ingredients_tokens) if ingredients_tokens else None,
            evidence_ids=ing_evidence_ids,
            capture_ids=ing_capture_ids
        ))
    else:
        final_candidates.append(FieldCandidate(field="FSSAI_INGREDIENTS", status="NOT_DETECTED"))

    if allergen_statement:
        final_candidates.append(FieldCandidate(
            field="FSSAI_ALLERGENS",
            status="DETECTED",
            raw_value=allergen_statement,
            evidence_ids=all_evidence_ids,
            capture_ids=all_capture_ids
        ))
    else:
        final_candidates.append(FieldCandidate(field="FSSAI_ALLERGENS", status="NOT_DETECTED"))

    if nutrition_detected:
        final_candidates.append(FieldCandidate(
            field="FSSAI_NUTRITION",
            status="DETECTED",
            raw_value=" | ".join(nut_text_lines) if nut_text_lines else "Nutritional Facts Panel Detected",
            evidence_ids=nut_evidence_ids,
            capture_ids=nut_capture_ids
        ))
    else:
        final_candidates.append(FieldCandidate(field="FSSAI_NUTRITION", status="NOT_DETECTED"))

    return final_candidates