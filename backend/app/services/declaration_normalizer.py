import re
from typing import Optional

from app.schemas.ocr import (
    MrpNormalized,
    NetQuantityNormalized,
    BusinessNormalized,
    DateNormalized,
    ConsumerCareNormalized,
    CountryOfOriginNormalized,
    CommonGenericNameNormalized,
    UnitSalePriceNormalized
)

def parse_mrp(text: str) -> Optional[MrpNormalized]:
    """
    Extracts the MRP value and currency from a string.
    Supports INR formats (Rs, Rs., ₹).
    """
    # Look for a number with optional decimals, possibly preceded by currency symbols
    # Ex: MRP Rs. 120.00, ₹120, Rs 120
    text_upper = text.upper()
    
    # Do not parse as MRP if it looks like a Unit Sale Price and lacks MRP keywords
    has_usp_pattern = bool(re.search(r"(?:/|PER)\s*(?:\d+(?:\.\d+)?)?\s*(G|GM|GRAM|KG|KILOGRAM|ML|MILLILITRE|L|LITRE|CM|CENTIMETRE|M|METRE|UNIT|NUMBER)\b", text_upper))
    if has_usp_pattern and "MRP" not in text_upper and "MAXIMUM RETAIL PRICE" not in text_upper:
        return None
        
    # Remove common extra words that might confuse the regex
    cleaned = re.sub(r"INCLUSIVE OF ALL TAXES|INCL\. OF ALL TAXES|MAXIMUM RETAIL PRICE|M\.R\.P\.", "", text_upper, flags=re.IGNORECASE)
    
    match = re.search(r"(?:RS\.?|₹|INR)?\s*(\d+(?:\.\d{1,2})?)(?:\s*/-)?", cleaned)
    if match:
        amount_str = match.group(1)
        try:
            amount = float(amount_str)
            return MrpNormalized(currency="INR", amount=amount)
        except ValueError:
            pass
    return None

def parse_net_quantity(text: str) -> Optional[NetQuantityNormalized]:
    """
    Extracts the numeric value and unit for Net Quantity.
    """
    # Look for a number followed by an optional space and a unit (G, KG, ML, L, CM, M, U, UNIT, etc.)
    match = re.search(r"(\d+(?:\.\d+)?)\s*(G|GM|KG|ML|L|CM|M|U|UNIT|NUMBER)\b", text, re.IGNORECASE)
    if match:
        try:
            value = float(match.group(1))
            unit = match.group(2).lower()
            return NetQuantityNormalized(value=value, unit=unit)
        except ValueError:
            pass
    return None


def parse_net_quantity_observation(text: str) -> Optional[NetQuantityNormalized]:
    """Preserve reliable labelled numeric evidence even when its unit is invalid.

    This is intentionally broader than ``parse_net_quantity`` and is only used
    after the extractor has identified an explicit net-quantity declaration.
    The validity service, rather than this parser, decides the legal result.
    """
    parsed = parse_net_quantity(text)
    if parsed is not None:
        return parsed
    if not re.search(r"\bNET\s*(?:QTY|QUANTITY|WEIGHT|WT|VOL(?:UME)?)\b", text, re.IGNORECASE):
        return None
    match = re.search(
        r"\bNET\s*(?:QTY|QUANTITY|WEIGHT|WT|VOL(?:UME)?)\b\s*:?-?\s*"
        r"(\d+(?:\.\d+)?)\s*([A-Z]+)?\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        return NetQuantityNormalized(
            value=float(match.group(1)),
            unit=(match.group(2) or "").lower(),
        )
    except ValueError:
        return None

def parse_business_declaration(text: str) -> Optional[BusinessNormalized]:
    """
    Extracts the role, name, address, and pin_code from a business declaration line.
    """
    text_upper = text.upper()
    
    role = "UNKNOWN"
    if re.search(r"^(?:[\s\W]*)(?:MFD|MFG|MANUFACTURED).{0,15}(?:BY|FOR)", text_upper):
        role = "MANUFACTURER"
    elif re.search(r"^(?:[\s\W]*)(?:PKD|PACKED).{0,10}(?:BY|FOR)", text_upper):
        role = "PACKER"
    elif re.search(r"^(?:[\s\W]*)(?:IMPORTED\.?\s*(?:BY|FOR)|IMPORTER)", text_upper):
        role = "IMPORTER"
    elif re.search(r"^(?:[\s\W]*)(?:MARKETED\.?\s*(?:BY|FOR)|MARKETER)", text_upper):
        role = "MARKETER"
        
    if role == "UNKNOWN":
        if any(k in text_upper for k in ["LTD", "PVT", "LIMITED", "CORP", "INC"]):
            role = "UNKNOWN"
        else:
            return None
         
    name = None
    address = None
    pin_code = None
    
    # Remove prefix (only the first occurrence to avoid destroying address lines)
    cleaned = re.sub(r"(?:MANUFACTURED|PACKED|IMPORTED|MARKETED|MFG|MFD|PKD)\.?\s*(?:BY|FOR)?\s*:?\s*", "", text, count=1, flags=re.IGNORECASE).strip()
    
    if cleaned and len(cleaned) > 2:
        lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
        if lines:
            first_line = lines[0]
            upper_first = first_line.upper()
            is_invalid = False
            
            # Numeric / License-like numbers (e.g. 123456)
            if bool(re.fullmatch(r"[\d\W]+", upper_first)):
                is_invalid = True
            # Country only
            elif upper_first in ["IN INDIA", "MADE IN INDIA", "PRODUCT OF INDIA", "INDIA"]:
                is_invalid = True
            # Cross references
            elif "SAME AS" in upper_first or "SEE ADDRESS" in upper_first or "REFER TO" in upper_first:
                is_invalid = True
            # Generic headings or instructions
            elif re.search(r"^(?:CONTACT|CONSUMER|NET QUANTITY|MRP|BEST BEFORE|USE BY|EXPIRY|DATE|INGREDIENTS|NUTRITION|LICENSE|LIC\.? NO\.?|BARCODE|ADDRESS:?$|ADDRESS\s*$)", upper_first):
                is_invalid = True
                
            if not is_invalid:
                name = first_line
                
            start_idx = 1 if name else 0
            addr_lines = lines[start_idx:]
            if addr_lines:
                address = "\n".join(addr_lines)
                pin_match = re.search(r"\b(\d{6})\b", address)
                if pin_match:
                    pin_code = pin_match.group(1)

    return BusinessNormalized(role=role, name=name, address=address, pin_code=pin_code, raw_text=text)

def parse_date_declaration(text: str) -> Optional[DateNormalized]:
    """
    Extracts date (month/year) or duration from a date declaration line.
    """
    text_upper = text.upper()
    
    date_type = "UNKNOWN"
    if "BEST BEFORE" in text_upper:
        date_type = "BEST_BEFORE"
    elif "USE BY" in text_upper:
        date_type = "USE_BY"
    elif "EXP" in text_upper or "EXPIRY" in text_upper:
        date_type = "EXPIRY"
    elif "PKD" in text_upper or "PACKED" in text_upper or "PACKING" in text_upper or "PACK" in text_upper:
        date_type = "PACKED"
    elif "MFG" in text_upper or "MANUFACTURE" in text_upper or "MFD" in text_upper:
        date_type = "MANUFACTURED"
    elif "IMPORTED" in text_upper or "IMPORT DATE" in text_upper:
        date_type = "IMPORTED"

    # DD/MM/YY or DD/MM/YYYY with / or - or . (supports trailing timestamps like 2608:15)
    match_dd_mm = re.search(r"(?:^|[^\d])([0-3]?\d)[-/.\s](0?[1-9]|1[0-2])[-/.\s](20\d{2}|\d{2})(?=(?:\d{2}:\d{2}|[^\d]|$))", text_upper)
    if match_dd_mm:
        year_str = match_dd_mm.group(3)
        year = int(year_str)
        if len(year_str) == 2:
            year += 2000
        d_type = date_type
        return DateNormalized(type=d_type, day=int(match_dd_mm.group(1)), month=int(match_dd_mm.group(2)), year=year)

    # MM/YYYY or MM-YYYY or MM.YYYY or MM/YY
    match_mm_yyyy = re.search(r"(?:^|[^\d])(0?[1-9]|1[0-2])[-/.\s](20\d{2}|\d{2})(?=(?:\d{2}:\d{2}|[^\d]|$))", text_upper)
    if match_mm_yyyy:
        year_str = match_mm_yyyy.group(2)
        year = int(year_str)
        if len(year_str) == 2:
            year += 2000
        d_type = date_type
        return DateNormalized(type=d_type, month=int(match_mm_yyyy.group(1)), year=year)
        
    # Month names (full and 3-letter abbreviation)
    month_map = {
        "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
        "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6,
        "JUL": 7, "JULY": 7, "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPTEMBER": 9,
        "OCT": 10, "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12
    }
    for m_name, m_num in month_map.items():
        match_mmm_yyyy = re.search(rf"\b{m_name}[,.\s]*(20\d{{2}}|\d{{2}})\b", text_upper)
        if match_mmm_yyyy:
            year_str = match_mmm_yyyy.group(1)
            year = int(year_str)
            if len(year_str) == 2:
                year += 2000
            d_type = date_type
            return DateNormalized(type=d_type, month=m_num, year=year)

    # Best Before Duration
    match_duration = re.search(r"\b(\d+)\s*(MONTHS?|DAYS?|YEARS?)\b", text_upper)
    if match_duration:
        duration = int(match_duration.group(1))
        unit = match_duration.group(2)
        if "MONTH" in unit:
            unit = "MONTH"
        elif "DAY" in unit:
            unit = "DAY"
        elif "YEAR" in unit:
            unit = "YEAR"
        d_type = date_type if date_type != "UNKNOWN" else "BEST_BEFORE"
        return DateNormalized(type=d_type, duration=duration, duration_unit=unit)

    return None


def parse_date_observation(text: str) -> Optional[DateNormalized]:
    """Preserve labelled calendar components that may be structurally invalid."""
    parsed = parse_date_declaration(text)
    if parsed is not None:
        return parsed
    text_upper = text.upper()
    if "BEST BEFORE" in text_upper:
        date_type = "BEST_BEFORE"
    elif "USE BY" in text_upper:
        date_type = "USE_BY"
    elif "EXP" in text_upper:
        date_type = "EXPIRY"
    elif any(token in text_upper for token in ("PKD", "PACKED", "PACKING")):
        date_type = "PACKED"
    elif any(token in text_upper for token in ("MFG", "MFD", "MANUFACTURE")):
        date_type = "MANUFACTURED"
    elif "IMPORTED" in text_upper or "IMPORT DATE" in text_upper:
        date_type = "IMPORTED"
    else:
        return None

    full_date = re.search(
        r"(?<!\d)(\d{1,2})[-/.\s](\d{1,2})[-/.\s](20\d{2}|\d{2})(?!\d)",
        text_upper,
    )
    if full_date:
        year_text = full_date.group(3)
        year = int(year_text) + (2000 if len(year_text) == 2 else 0)
        return DateNormalized(
            type=date_type,
            day=int(full_date.group(1)),
            month=int(full_date.group(2)),
            year=year,
        )

    month_year = re.search(r"(?<!\d)(\d{1,2})[-/.\s](20\d{2}|\d{2})(?!\d)", text_upper)
    if month_year:
        year_text = month_year.group(2)
        year = int(year_text) + (2000 if len(year_text) == 2 else 0)
        return DateNormalized(type=date_type, month=int(month_year.group(1)), year=year)
    return None

def parse_consumer_care(text: str) -> Optional[ConsumerCareNormalized]:
    """
    Extracts email and phone from consumer care text.
    """
    email = None
    phone = None
    
    # Email match
    match_email = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", text)
    if match_email:
        email = match_email.group(1)
        
    # Phone match
    # Look for Indian numbers, toll free, STD landlines, mobile, with common labels (Ph, Tel, Phone, Contact)
    match_phone = re.search(
        r"(?:(?:PH(?:ONE|\.)?|TEL(?:EPHONE)?|CONTACT|CALL|TOLL\s*FREE|HELPLINE)\s*:?\s*)?"
        r"(?:"
        r"(?:1800[-\s]?\d{3,4}[-\s]?\d{3,4})"                   # Toll-free (e.g. 1800 555 0199, 1800-123-4567)
        r"|(?:\+91[-\s]?(?:\(\d{2,4}\)[-\s]?|\d{2,4}[-\s]?)?\d{3,5}[-\s]?\d{4,5})" # +91 formatted
        r"|(?:\b0\d{2,4}[-\s]?\d{3,4}[-\s]?\d{3,4}\b)"          # STD landline (e.g. 011-23456789, 022 2685 1234)
        r"|(?:\b[6-9]\d{4}[-\s]?\d{5}\b)"                      # 10-digit Indian mobile 5-5 (e.g. 98765 43210)
        r"|(?:\b[6-9]\d{2}[-\s]?\d{3}[-\s]?\d{4}\b)"           # 10-digit Indian mobile 3-3-4 (e.g. 987 654 3210)
        r"|(?:\b[6-9]\d{9}\b)"                                 # 10-digit Indian mobile contiguous
        r"|(?:\b1800\d{6,7}\b)"                                # 1800 contiguous
        r")",
        text,
        re.IGNORECASE
    )
    if match_phone:
        raw_phone = match_phone.group(0)
        clean_phone = re.sub(
            r"^(?:PH(?:ONE|\.)?|TEL(?:EPHONE)?|CONTACT|CALL|TOLL\s*FREE|HELPLINE)\s*:?\s*",
            "",
            raw_phone,
            flags=re.IGNORECASE
        ).strip()
        clean_phone_val = clean_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if len(clean_phone_val) >= 7:
            phone = clean_phone_val
        
    if email or phone:
        return ConsumerCareNormalized(email=email, phone=phone)
        
    return None

def parse_country_of_origin(text: str) -> Optional[CountryOfOriginNormalized]:
    """
    Extracts the country of origin, manufacture, or assembly.
    """
    text_upper = text.upper()
    
    declaration_type = "ORIGIN"
    if "MANUFACTURE" in text_upper:
        declaration_type = "MANUFACTURE"
    elif "ASSEMBLY" in text_upper:
        declaration_type = "ASSEMBLY"
        
    # Remove the heading
    cleaned = re.sub(r"COUNTRY\s+OF\s+(?:ORIGIN|MANUFACTURE|ASSEMBLY)\s*:?\s*", "", text, count=1, flags=re.IGNORECASE)
    cleaned = re.sub(r"MADE\s+IN\s*:?\s*", "", cleaned, count=1, flags=re.IGNORECASE).strip()
    
    if cleaned and len(cleaned) >= 2:
        return CountryOfOriginNormalized(
            declaration_type=declaration_type,
            country_text=cleaned,
            raw_text=text
        )
        
    return None

def parse_common_generic_name(text: str) -> Optional[CommonGenericNameNormalized]:
    """
    Extracts the common or generic name, stripping prefixes.
    """
    # Remove headings like COMMON NAME, GENERIC NAME, NAME OF COMMODITY, COMMODITY, PRODUCT NAME, PRODUCT, ITEM
    cleaned = re.sub(
        r"^(?:COMMON\s+NAME|GENERIC\s+NAME|NAME\s+OF\s+COMMODITY|COMMODITY\s*NAME|COMMODITY|PRODUCT\s*NAME|PRODUCT|ITEM\s*NAME|ITEM|ARTICLE)\s*:?\s*", 
        "", 
        text, 
        count=1, 
        flags=re.IGNORECASE
    ).strip()
    
    if cleaned and len(cleaned) >= 2:
        return CommonGenericNameNormalized(name_text=cleaned)
        
    return None

def parse_unit_sale_price(text: str) -> Optional[UnitSalePriceNormalized]:
    """
    Extracts the Unit Sale Price amount and denominator.
    Expects formats like Rs 1.50/g, ₹10/kg, Rs. 5 per unit.
    """
    import re
    # Clean common words
    cleaned = re.sub(r"UNIT\s+SALE\s+PRICE|USP", "", text, flags=re.IGNORECASE).strip()
    
    # regex for USP: (Rs|₹)? [amount] (per|/) [quantity]? [unit]
    # e.g., ₹12.50/kg, Rs. 0.25/g, Rs. 5.00 per unit, 1.10/ml
    # we need to be careful with per_quantity which might not be present (defaults to 1.0)
    match = re.search(
        r"(?:RS\.?|₹|INR)?\s*(\d+(?:\.\d{1,2})?)\s*(?:/|PER)\s*(\d+(?:\.\d+)?)?\s*(G|GM|GRAM|KG|KILOGRAM|ML|MILLILITRE|L|LITRE|CM|CENTIMETRE|M|METRE|U|UNIT|NUMBER|PCS)\b",
        cleaned,
        re.IGNORECASE
    )
    if match:
        amount_str = match.group(1)
        per_qty_str = match.group(2)
        unit_str = match.group(3).upper()
        
        try:
            amount = float(amount_str)
            per_quantity = float(per_qty_str) if per_qty_str else 1.0
            
            # Normalize unit
            normalized_unit = "UNKNOWN"
            if unit_str in ("G", "GM", "GRAM"):
                normalized_unit = "g"
            elif unit_str in ("KG", "KILOGRAM"):
                normalized_unit = "kg"
            elif unit_str in ("ML", "MILLILITRE"):
                normalized_unit = "ml"
            elif unit_str in ("L", "LITRE"):
                normalized_unit = "L"
            elif unit_str in ("CM", "CENTIMETRE"):
                normalized_unit = "cm"
            elif unit_str in ("M", "METRE"):
                normalized_unit = "m"
            elif unit_str in ("U", "UNIT", "NUMBER", "PCS"):
                normalized_unit = "unit"
                
            if normalized_unit != "UNKNOWN":
                return UnitSalePriceNormalized(
                    amount=amount,
                    currency="INR",
                    per_quantity=per_quantity,
                    per_unit=normalized_unit
                )
        except ValueError:
            pass
            
    return None
