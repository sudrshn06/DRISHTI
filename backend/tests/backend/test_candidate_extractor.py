import pytest
from app.schemas.ocr import OcrLine, BusinessNormalized, DateNormalized, NetQuantityNormalized, CountryOfOriginNormalized
from app.services.candidate_extractor import extract_candidates


def make_line(text):
    return OcrLine(
        text=text,
        confidence=0.99,
        polygon=[[0, 0], [1, 0], [1, 1], [0, 1]]
    )


def test_extract_business_boundary_same_line():
    lines = [
        make_line("Manufactured by: Alpha Foods Pvt Ltd"),
        make_line("123456"),
        make_line("RECYCLABLE")
    ]

    candidates = extract_candidates(lines, {})
    biz_cands = [
        c for c in candidates
        if c.field == "MANUFACTURER_PACKER_IMPORTER"
    ]

    assert len(biz_cands) == 1
    assert biz_cands[0].status == "DETECTED"

    value = biz_cands[0].normalized_value
    assert isinstance(value, BusinessNormalized)
    assert value.name is not None
    assert value.name.upper() == "ALPHA FOODS PVT LTD"

    # Should NOT have absorbed 123456


def test_extract_business_boundary_next_line():
    lines = [
        make_line("Manufactured by:"),
        make_line("Alpha Foods Pvt Ltd"),
        make_line("RECYCLABLE")
    ]

    candidates = extract_candidates(lines, {})
    biz_cands = [
        c for c in candidates
        if c.field == "MANUFACTURER_PACKER_IMPORTER"
    ]

    assert len(biz_cands) == 1
    assert biz_cands[0].status == "DETECTED"

    value = biz_cands[0].normalized_value
    assert isinstance(value, BusinessNormalized)
    assert value.name is not None
    assert value.name.upper() == "ALPHA FOODS PVT LTD"


def test_extract_dates_single():
    lines = [
        make_line("MFD25/03/2608:15")
    ]

    candidates = extract_candidates(lines, {})
    date_cands = [c for c in candidates if c.field == "MONTH_YEAR"]

    assert len(date_cands) == 1
    assert date_cands[0].status == "DETECTED"
    assert isinstance(date_cands[0].normalized_value, DateNormalized)
    assert date_cands[0].normalized_value.type == "MANUFACTURED"
    assert date_cands[0].normalized_value.day == 25
    assert date_cands[0].normalized_value.month == 3
    assert date_cands[0].normalized_value.year == 2026


def test_extract_dates_multiple_independent():
    lines = [
        make_line("MFD 14/08/26"),
        make_line("USE BY 20/11/26")
    ]

    candidates = extract_candidates(lines, {})
    date_cands = [c for c in candidates if c.field == "MONTH_YEAR"]

    assert len(date_cands) == 2

    assert date_cands[0].status == "DETECTED"
    assert isinstance(date_cands[0].normalized_value, DateNormalized)
    assert date_cands[0].normalized_value.type == "MANUFACTURED"

    assert date_cands[1].status == "DETECTED"
    assert isinstance(date_cands[1].normalized_value, DateNormalized)
    assert date_cands[1].normalized_value.type == "USE_BY"


def test_extract_dates_multiple_with_review():
    lines = [
        make_line("MFD 14/08/26"),
        make_line("USE BY22107/26")
    ]

    candidates = extract_candidates(lines, {})
    date_cands = [c for c in candidates if c.field == "MONTH_YEAR"]

    assert len(date_cands) == 2

    assert date_cands[0].status == "DETECTED"
    assert isinstance(date_cands[0].normalized_value, DateNormalized)
    assert date_cands[0].normalized_value.type == "MANUFACTURED"

    assert date_cands[1].status == "REVIEW_REQUIRED"
    assert date_cands[1].normalized_value is None


def test_extract_dates_expiry():
    lines = [
        make_line("EXP 05/12/2027")
    ]

    candidates = extract_candidates(lines, {})
    date_cands = [c for c in candidates if c.field == "MONTH_YEAR"]

    assert len(date_cands) == 1
    assert date_cands[0].status == "DETECTED"
    assert isinstance(date_cands[0].normalized_value, DateNormalized)
    assert date_cands[0].normalized_value.type == "EXPIRY"
    assert date_cands[0].normalized_value.day == 5
    assert date_cands[0].normalized_value.month == 12
    assert date_cands[0].normalized_value.year == 2027


def test_lookahead_stops_at_heading():
    lines = [
        make_line("MFD"),
        make_line("USE BY 12/2026")
    ]

    candidates = extract_candidates(lines, {})
    date_cands = [c for c in candidates if c.field == "MONTH_YEAR"]

    # Should flag MFD as REVIEW_REQUIRED, and USE BY as DETECTED
    assert len(date_cands) == 2
    assert date_cands[0].status == "REVIEW_REQUIRED"
    assert date_cands[1].status == "DETECTED"


def test_disambiguate_mfd_by_from_date():
    lines = [
        make_line("MFD. BY: Alpha Foods Pvt Ltd")
    ]

    candidates = extract_candidates(lines, {})
    biz_cands = [
        c for c in candidates
        if c.field == "MANUFACTURER_PACKER_IMPORTER"
    ]
    date_cands = [c for c in candidates if c.field == "MONTH_YEAR"]

    assert len(biz_cands) == 1
    assert biz_cands[0].status == "DETECTED"

    # Must NOT create a MONTH_YEAR candidate just because it contains MFD
    assert len(date_cands) == 1
    assert date_cands[0].status == "NOT_DETECTED"


def test_disambiguate_mfg_by_from_date():
    lines = [
        make_line("MFG BY Beta Consumer Ltd")
    ]

    candidates = extract_candidates(lines, {})
    biz_cands = [
        c for c in candidates
        if c.field == "MANUFACTURER_PACKER_IMPORTER"
    ]
    date_cands = [c for c in candidates if c.field == "MONTH_YEAR"]

    assert len(biz_cands) == 1
    assert biz_cands[0].status == "DETECTED"

    assert len(date_cands) == 1
    assert date_cands[0].status == "NOT_DETECTED"


def test_mfg_date_recognized():
    lines = [
        make_line("MFG DATE: 14/08/2026")
    ]

    candidates = extract_candidates(lines, {})
    date_cands = [c for c in candidates if c.field == "MONTH_YEAR"]

    assert len(date_cands) == 1
    assert date_cands[0].status == "DETECTED"
    assert isinstance(date_cands[0].normalized_value, DateNormalized)
    assert date_cands[0].normalized_value.day == 14


def test_mfd_no_day():
    lines = [
        make_line("MFD 08/2026")
    ]

    candidates = extract_candidates(lines, {})
    date_cands = [c for c in candidates if c.field == "MONTH_YEAR"]

    assert len(date_cands) == 1
    assert date_cands[0].status == "DETECTED"
    assert isinstance(date_cands[0].normalized_value, DateNormalized)
    assert date_cands[0].normalized_value.month == 8
    assert date_cands[0].normalized_value.day is None


def test_business_regression_same_as():
    lines = [
        make_line("MANUFACTURED BY"),
        make_line("1234567890"),
        make_line("IN INDIA"),
        make_line("CONTACT CONSUMER CARE"),
        make_line("ADDRESS: SAME AS MANUFACTURED BY ADDRESS")
    ]

    candidates = extract_candidates(lines, {})
    biz_cands = [
        c for c in candidates
        if c.field == "MANUFACTURER_PACKER_IMPORTER"
    ]

    assert len(biz_cands) == 1
    assert biz_cands[0].status == "REVIEW_REQUIRED"
    assert isinstance(biz_cands[0].normalized_value, BusinessNormalized)
    assert biz_cands[0].normalized_value.name is None
    assert biz_cands[0].raw_value == "MANUFACTURED BY"


def test_business_regression_valid_next_line():
    lines = [
        make_line("MANUFACTURED BY"),
        make_line("Example Foods Private Limited")
    ]

    candidates = extract_candidates(lines, {})
    biz_cands = [
        c for c in candidates
        if c.field == "MANUFACTURER_PACKER_IMPORTER"
    ]

    assert len(biz_cands) == 1
    assert biz_cands[0].status == "DETECTED"

    value = biz_cands[0].normalized_value
    assert isinstance(value, BusinessNormalized)
    assert value.name is not None
    assert value.name.upper() == "EXAMPLE FOODS PRIVATE LIMITED"


def test_business_regression_numeric_contact():
    lines = [
        make_line("MANUFACTURED BY"),
        make_line("123456"),
        make_line("CONTACT CUSTOMER CARE")
    ]

    candidates = extract_candidates(lines, {})
    biz_cands = [
        c for c in candidates
        if c.field == "MANUFACTURER_PACKER_IMPORTER"
    ]

    assert len(biz_cands) == 1
    assert biz_cands[0].status == "REVIEW_REQUIRED"
    assert isinstance(biz_cands[0].normalized_value, BusinessNormalized)
    assert biz_cands[0].normalized_value.name is None
    assert biz_cands[0].raw_value == "MANUFACTURED BY"


def test_nq_priority_anchored_over_standalone():
    lines = [
        make_line("NUTRITION FACTS"),
        make_line("TOTAL SUGARS"),
        make_line("10.9g"),
        make_line("NET QUANTITY:"),
        make_line("300 ml")
    ]
    candidates = extract_candidates(lines, {})
    nq = next(c for c in candidates if c.field == "NET_QUANTITY")
    assert nq.status == "DETECTED"
    assert isinstance(nq.normalized_value, NetQuantityNormalized)
    assert nq.normalized_value.value == 300.0
    assert nq.normalized_value.unit == "ml"

def test_nq_standalone_no_context():
    lines = [
        make_line("10.9g")
    ]
    candidates = extract_candidates(lines, {})
    nq = next(c for c in candidates if c.field == "NET_QUANTITY")
    assert nq.status == "REVIEW_REQUIRED"
    assert isinstance(nq.normalized_value, NetQuantityNormalized)
    assert nq.normalized_value.value == 10.9
    assert nq.normalized_value.unit == "g"

def test_nq_simple_explicit():
    lines = [
        make_line("NET QUANTITY"),
        make_line("750 ml")
    ]
    candidates = extract_candidates(lines, {})
    nq = next(c for c in candidates if c.field == "NET_QUANTITY")
    assert nq.status == "DETECTED"
    assert isinstance(nq.normalized_value, NetQuantityNormalized)
    assert nq.normalized_value.value == 750.0
    assert nq.normalized_value.unit == "ml"

def test_nq_simple_explicit_inline():
    lines = [
        make_line("NET QUANTITY: 500 g")
    ]
    candidates = extract_candidates(lines, {})
    nq = next(c for c in candidates if c.field == "NET_QUANTITY")
    assert nq.status == "DETECTED"
    assert isinstance(nq.normalized_value, NetQuantityNormalized)
    assert nq.normalized_value.value == 500.0
    assert nq.normalized_value.unit == "g"

def test_nq_conflicting_anchored():
    lines = [
        make_line("NET QUANTITY: 500 ml"),
        make_line("NET QUANTITY: 750 ml")
    ]
    candidates = extract_candidates(lines, {})
    nq = next(c for c in candidates if c.field == "NET_QUANTITY")
    assert nq.status == "REVIEW_REQUIRED"
    assert nq.raw_value is not None
    assert "conflicting" in nq.raw_value.lower()

def test_extract_business_multiple_roles():
    lines = [
        make_line("Manufactured by:"),
        make_line("Company A"),
        make_line("Mumbai, Maharashtra 400001"),
        make_line("Imported by:"),
        make_line("Company B"),
        make_line("Delhi 110001")
    ]
    candidates = extract_candidates(lines, {})
    biz_cands = [c for c in candidates if c.field == "MANUFACTURER_PACKER_IMPORTER"]
    
    assert len(biz_cands) == 2
    
    mfg = biz_cands[0].normalized_value
    assert mfg.role == "MANUFACTURER"
    assert mfg.name == "Company A"
    assert mfg.pin_code == "400001"
    
    imp = biz_cands[1].normalized_value
    assert imp.role == "IMPORTER"
    assert imp.name == "Company B"
    assert imp.pin_code == "110001"

def test_extract_country_of_origin():
    lines = [
        make_line("MADE IN"),
        make_line("INDIA")
    ]
    candidates = extract_candidates(lines, {})
    coo_cands = [c for c in candidates if c.field == "COUNTRY_OF_ORIGIN"]
    assert len(coo_cands) == 1
    assert coo_cands[0].status == "DETECTED"
    assert isinstance(coo_cands[0].normalized_value, CountryOfOriginNormalized)
    assert coo_cands[0].normalized_value.country_text == "INDIA"
    assert coo_cands[0].normalized_value.declaration_type == "ORIGIN"

def test_extract_country_of_origin_inline():
    lines = [
        make_line("COUNTRY OF MANUFACTURE: USA")
    ]
    candidates = extract_candidates(lines, {})
    coo_cands = [c for c in candidates if c.field == "COUNTRY_OF_ORIGIN"]
    assert len(coo_cands) == 1
    assert coo_cands[0].status == "DETECTED"
    assert isinstance(coo_cands[0].normalized_value, CountryOfOriginNormalized)
    assert coo_cands[0].normalized_value.country_text == "USA"
    assert coo_cands[0].normalized_value.declaration_type == "MANUFACTURE"

def test_extract_country_of_origin_missing_value():
    lines = [
        make_line("MADE IN")
    ]
    candidates = extract_candidates(lines, {})
    coo_cands = [c for c in candidates if c.field == "COUNTRY_OF_ORIGIN"]
    assert len(coo_cands) == 1
    assert coo_cands[0].status == "REVIEW_REQUIRED"