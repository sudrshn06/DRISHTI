# DRISHTI Current Rule Mapping

This document maps the explicitly supported DRISHTI extraction fields to the corrected chronology of Legal Metrology (Packaged Commodities) Rules, 2011 provisions.

---

## 1. CONSUMER_CARE
- **FIELD**: `CONSUMER_CARE`
- **SOURCE DOCUMENT**: LMPC (Amendment) Rules, 2015 (G.S.R. 385(E))
- **RULE / SUB-RULE**: Rule 6(2)
- **CURRENT TEXT EFFECT**: Substitutes Rule 6(2) to explicitly require the consumer-complaint contact declaration to include name/address, telephone number, and e-mail address.
- **EFFECTIVE FROM**: 2016-01-01
- **APPLICABILITY CONDITIONS**: Applies to all retail pre-packaged commodities.
- **EVIDENCE NEEDED**: Name/address, telephone number, and e-mail address for consumer complaints.
- **CAN DRISHTI CURRENTLY EVALUATE?**: PARTIAL
- **UNRESOLVED ISSUE**: DRISHTI currently extracts the text block generically. It needs explicit sub-parsing to deterministically confirm the presence of *all three* elements (name/address, telephone, e-mail) as legally required by G.S.R. 385(E). 

---

## 2. MRP (Maximum Retail Price)
- **FIELD**: `MRP`
- **SOURCE DOCUMENT**: LMPC (Amendment) Rules, 2021 (G.S.R. 779(E)) & LMPC (Amendment) Rules, 2022 (G.S.R. 226(E))
- **RULE / SUB-RULE**: Rule 6(1)(e)
- **CURRENT TEXT EFFECT**: MRP must be declared in Indian currency inclusive of all taxes. Dual MRPs on identical commodities are banned (via 2017 amendment). 
- **EFFECTIVE FROM**: 2022-10-01 (as amended by G.S.R. 226(E))
- **APPLICABILITY CONDITIONS**: All pre-packaged commodities intended for retail sale, barring specific exemptions.
- **EVIDENCE NEEDED**: The declared retail sale price in Indian currency.
- **CAN DRISHTI CURRENTLY EVALUATE?**: PARTIAL
- **UNRESOLVED ISSUE**: `NEEDS_LEGAL_VERIFICATION` — Does current Rule 6(1)(e) strictly mandate the exact literal textual phrase `"inclusive of all taxes"` to appear on the package, or is it legally sufficient that the declared price is defined under the Act as being inclusive of all taxes? (Must not encode as a FAIL until verified).

---

## 3. NET_QUANTITY
- **FIELD**: `NET_QUANTITY`
- **SOURCE DOCUMENT**: LMPC (Amendment) Rules, 2021 (G.S.R. 779(E)) & LMPC Rules, 2011
- **RULE / SUB-RULE**: Rule 6(1)(c) and Rule 11
- **CURRENT TEXT EFFECT**: Must declare the net quantity in standard units. The 2021 amendment removed Schedule II (standard pack sizes), allowing any size, but requires Unit Sale Price alongside it.
- **EFFECTIVE FROM**: 2022-10-01
- **APPLICABILITY CONDITIONS**: All retail packages.
- **EVIDENCE NEEDED**: A numerical value and a valid standard unit of weight, measure, or number.
- **CAN DRISHTI CURRENTLY EVALUATE?**: YES
- **UNRESOLVED ISSUE**: None. Deterministic evaluation for value presence and allowed units is fully possible.

---

## 4. MANUFACTURER_PACKER_IMPORTER
- **FIELD**: `MANUFACTURER_PACKER_IMPORTER`
- **SOURCE DOCUMENT**: LMPC Rules, 2011 (Base version) & LMPC (Amendment) Rules, 2017 (G.S.R. 629(E))
- **RULE / SUB-RULE**: Rule 6(1)(a) and Rule 10
- **CURRENT TEXT EFFECT**: Must declare the name and address of the manufacturer (and packer, if different) or importer. The 2017 amendment heavily modified formatting and address definitions.
- **EFFECTIVE FROM**: 2018-01-01 (for 2017 amendments)
- **APPLICABILITY CONDITIONS**: All retail packages.
- **EVIDENCE NEEDED**: Entity name, role (Manufacturer/Packer/Importer), and an address sufficient to identify the premises.
- **CAN DRISHTI CURRENTLY EVALUATE?**: PARTIAL
- **UNRESOLVED ISSUE**: What constitutes a legally "complete" address for deterministic evaluation (e.g., is a PIN code strictly mandated to trigger a PASS, or does a substantial text block following "Manufactured by" suffice)?

---

## 5. Date Declarations
- **FIELD**: `MANUFACTURE_DATE` / `PACKING_DATE` / `IMPORT_DATE`
- **SOURCE DOCUMENT**: LMPC Rules, 2011 (Base version) & LMPC (Amendment) Rules, 2017 (G.S.R. 629(E))
- **RULE / SUB-RULE**: Rule 6(1)(d)
- **CURRENT TEXT EFFECT**: Requires the month and year in which the commodity is manufactured, pre-packed, or imported.
- **EFFECTIVE FROM**: 2018-01-01 (for 2017 amendments)
- **APPLICABILITY CONDITIONS**: All retail packages.
- **EVIDENCE NEEDED**: Clear indication of month and year contextually linked to manufacture, packing, or import.
- **CAN DRISHTI CURRENTLY EVALUATE?**: YES
- **UNRESOLVED ISSUE**: None for generic presence evaluation.
