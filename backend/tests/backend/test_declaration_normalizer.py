import pytest
from app.services.declaration_normalizer import (
    parse_mrp,
    parse_net_quantity,
    parse_business_declaration,
    parse_date_declaration,
    parse_consumer_care,
    parse_country_of_origin
)
from app.schemas.ocr import (
    MrpNormalized,
    NetQuantityNormalized,
    BusinessNormalized,
    DateNormalized,
    ConsumerCareNormalized,
    CountryOfOriginNormalized
)

def test_parse_mrp():
    # Test valid MRPs
    assert parse_mrp("MRP ₹120") == MrpNormalized(currency="INR", amount=120.0)
    assert parse_mrp("MRP Rs.120") == MrpNormalized(currency="INR", amount=120.0)
    assert parse_mrp("MRP Rs 120") == MrpNormalized(currency="INR", amount=120.0)
    assert parse_mrp("M.R.P. ₹120.00") == MrpNormalized(currency="INR", amount=120.0)
    assert parse_mrp("Maximum Retail Price: Rs. 120") == MrpNormalized(currency="INR", amount=120.0)
    assert parse_mrp("Maximum Retail Price ₹120/-") == MrpNormalized(currency="INR", amount=120.0)
    assert parse_mrp("MRP: 120.00") == MrpNormalized(currency="INR", amount=120.0)
    assert parse_mrp("MRP ₹120 inclusive of all taxes") == MrpNormalized(currency="INR", amount=120.0)
    assert parse_mrp("MRP Rs. 99.50 incl. of all taxes") == MrpNormalized(currency="INR", amount=99.5)
    
    # Test invalid MRPs
    assert parse_mrp("MRP") is None
    assert parse_mrp("MAXIMUM RETAIL PRICE") is None
    assert parse_mrp("Just some text") is None

def test_parse_net_quantity():
    # Test valid net quantities
    assert parse_net_quantity("Net Qty 500 g") == NetQuantityNormalized(value=500.0, unit="g")
    assert parse_net_quantity("Net Qty. 500g") == NetQuantityNormalized(value=500.0, unit="g")
    assert parse_net_quantity("Net Weight 1 kg") == NetQuantityNormalized(value=1.0, unit="kg")
    assert parse_net_quantity("Net Wt 250 g") == NetQuantityNormalized(value=250.0, unit="g")
    assert parse_net_quantity("Net Volume 500 ml") == NetQuantityNormalized(value=500.0, unit="ml")
    assert parse_net_quantity("Net Vol. 1 L") == NetQuantityNormalized(value=1.0, unit="l")
    assert parse_net_quantity("Net Contents 200 g") == NetQuantityNormalized(value=200.0, unit="g")
    assert parse_net_quantity("200 g") == NetQuantityNormalized(value=200.0, unit="g")
    assert parse_net_quantity("500 ml") == NetQuantityNormalized(value=500.0, unit="ml")
    assert parse_net_quantity("1.5 L") == NetQuantityNormalized(value=1.5, unit="l")
    assert parse_net_quantity("2 kg") == NetQuantityNormalized(value=2.0, unit="kg")
    
    # Test invalid net quantities
    assert parse_net_quantity("Net Qty") is None
    assert parse_net_quantity("500") is None
    assert parse_net_quantity("Weight") is None

def test_parse_business_declaration():
    # Roles
    assert parse_business_declaration("Manufactured by").role == "MANUFACTURER"
    assert parse_business_declaration("Mfd. by").role == "MANUFACTURER"
    assert parse_business_declaration("Mfg. by").role == "MANUFACTURER"
    assert parse_business_declaration("Manufactured & Packed by").role == "MANUFACTURER"
    assert parse_business_declaration("Packed by").role == "PACKER"
    assert parse_business_declaration("Pkd. by").role == "PACKER"
    assert parse_business_declaration("Marketed by").role == "MARKETER"
    assert parse_business_declaration("Imported by").role == "IMPORTER"
    assert parse_business_declaration("Importer").role == "IMPORTER"
    
    # Single line parsing
    res = parse_business_declaration("Manufactured by ABC Foods Pvt. Ltd.")
    assert res.role == "MANUFACTURER"
    assert res.name == "ABC Foods Pvt. Ltd."
    
    res2 = parse_business_declaration("Packed for XYZ India Ltd.")
    assert res2.role == "PACKER"
    assert res2.name == "XYZ India Ltd."
    
    # Contextual check
    assert parse_business_declaration("LTD").role == "UNKNOWN"

    # 1. manufacturer + multiline address + PIN extracts correctly
    res3 = parse_business_declaration("Manufactured by:\nABC Foods Pvt. Ltd.\nPlot 12, Industrial Estate\nHosur, Tamil Nadu - 635126")
    assert res3.role == "MANUFACTURER"
    assert res3.name == "ABC Foods Pvt. Ltd."
    assert "Plot 12, Industrial Estate" in res3.address
    assert res3.pin_code == "635126"

    # 2. address without PIN remains structured address evidence
    res4 = parse_business_declaration("Packed by:\nXYZ India Ltd.\nMumbai, Maharashtra")
    assert res4.role == "PACKER"
    assert res4.name == "XYZ India Ltd."
    assert "Mumbai" in res4.address
    assert res4.pin_code is None

    # 3. Phone number is not PIN
    # Even if in address, phone numbers don't match exactly 6 digits \b(\d{6})\b
    res5 = parse_business_declaration("Imported by:\nGlobal Traders\nDelhi\nPhone: 9876543210")
    assert res5.role == "IMPORTER"
    assert res5.pin_code is None

    # 4. ordinary prose containing "packed" remains rejected
    # "packed" might be caught by regex if not careful, but the parse_business_declaration checks the first line.
    res6 = parse_business_declaration("These items are packed tightly for freshness.")
    # The regex requires Manufactured/Packed By/For.
    assert res6 is None

def test_parse_date_declaration():
    # Formats
    assert parse_date_declaration("MFG 08/2026") == DateNormalized(type="MANUFACTURED", month=8, year=2026)
    assert parse_date_declaration("MFD 08/2026") == DateNormalized(type="MANUFACTURED", month=8, year=2026)
    assert parse_date_declaration("PKD 08/2026") == DateNormalized(type="PACKED", month=8, year=2026)
    assert parse_date_declaration("Packed on 08/2026") == DateNormalized(type="PACKED", month=8, year=2026)
    assert parse_date_declaration("Mfg Date: AUG 2026") == DateNormalized(type="MANUFACTURED", month=8, year=2026)
    assert parse_date_declaration("Date of Manufacture: 08-2026") == DateNormalized(type="MANUFACTURED", month=8, year=2026)
    assert parse_date_declaration("EXP 07/2027") == DateNormalized(type="EXPIRY", month=7, year=2027)
    assert parse_date_declaration("Expiry: JUL 2027") == DateNormalized(type="EXPIRY", month=7, year=2027)
    assert parse_date_declaration("Use By 08/2027") == DateNormalized(type="USE_BY", month=8, year=2027)
    
    # Regression tests
    assert parse_date_declaration("MFD25/03/2608:15") == DateNormalized(type="MANUFACTURED", day=25, month=3, year=2026)
    assert parse_date_declaration("MFD 25/03/26") == DateNormalized(type="MANUFACTURED", day=25, month=3, year=2026)
    assert parse_date_declaration("MFG 25/03/2026") == DateNormalized(type="MANUFACTURED", day=25, month=3, year=2026)
    assert parse_date_declaration("PKD 25/03/26") == DateNormalized(type="PACKED", day=25, month=3, year=2026)
    assert parse_date_declaration("USE BY 22/07/26") == DateNormalized(type="USE_BY", day=22, month=7, year=2026)
    assert parse_date_declaration("USE BY22107/26") is None
    
    # Invalid
    assert parse_date_declaration("random string") is None

def test_parse_consumer_care():
    assert parse_consumer_care("care@example.com") == ConsumerCareNormalized(email="care@example.com", phone=None)
    assert parse_consumer_care("1800-123-4567") == ConsumerCareNormalized(email=None, phone="18001234567")
    assert parse_consumer_care("+91 98765 43210") == ConsumerCareNormalized(email=None, phone="+919876543210")
    
    # Both
    res = parse_consumer_care("Email: care@example.in, Phone: 1800 123 4567")
    assert res.email == "care@example.in"
    assert res.phone == "18001234567"
    
    assert parse_consumer_care("Just some text") is None

def test_parse_country_of_origin():
    # Valid declarations
    res1 = parse_country_of_origin("COUNTRY OF ORIGIN: CHINA")
    assert res1.declaration_type == "ORIGIN"
    assert res1.country_text == "CHINA"

    res2 = parse_country_of_origin("MADE IN VIETNAM")
    assert res2.declaration_type == "ORIGIN"
    assert res2.country_text == "VIETNAM"

    res3 = parse_country_of_origin("Country of Manufacture: USA")
    assert res3.declaration_type == "MANUFACTURE"
    assert res3.country_text == "USA"

    res4 = parse_country_of_origin("COUNTRY OF ASSEMBLY: MEXICO")
    assert res4.declaration_type == "ASSEMBLY"
    assert res4.country_text == "MEXICO"

    # Multiline or trailing text
    res5 = parse_country_of_origin("MADE IN: \nITALY")
    assert res5.country_text == "ITALY"

    # Missing country (too short)
    res6 = parse_country_of_origin("MADE IN ")
    assert res6 is None

