# Absence-evaluation safety boundary

## Current Stage 1.5 invariant

DRISHTI Stage 1.5 must not infer that a statutory declaration is legally absent from the current capture plan. The active plan remains configured as `absence_evaluation_eligible=False`. Completing the requested front and back photographs therefore completes the capture workflow, but it does not establish full-package coverage for an absence finding.

PaddleOCR remains the machine-observation engine. Gemini output remains advisory and outside authoritative compliance inputs. Deterministic Legal Metrology and FSSAI rules remain authoritative, and an authenticated officer must review package information and explicitly approve finalization and any external portal handoff.

## Required surface coverage

An absence evaluation may only become eligible in a future, separately approved capture plan when the plan defines every package surface or declaration-bearing area required by the particular rule. The plan must account for the principal display panel, rear panel, side panels, top, bottom, seams, wrap-around labels, inserts, tags, multi-piece or group-package components, and any rule-specific alternate location.

Coverage must be recorded per required surface, not inferred from the number of photographs. Overlapping views do not prove that an unseen surface was covered. Curved, reflective, folded, obscured, damaged, or unusually shaped packaging requires additional views. If any required surface is missing or uncertain, evidence sufficiency remains `INSUFFICIENT_FOR_ABSENCE_EVALUATION` and declaration results must remain review-oriented rather than becoming a legal absence or failure.

## Usable image quality

Every photograph relied on for surface coverage must be usable for the declaration being evaluated. At minimum, the relevant region must be in frame, sufficiently sharp, adequately exposed, free from blocking glare, and captured at a resolution that lets an officer inspect the printed characters. A technically accepted image is not automatically usable for every declaration on that surface.

Clipped text, blur, glare, perspective distortion, occlusion, tiny text, low OCR confidence, an OCR result with no text, or a failed processing pipeline cannot support an absence conclusion. The system must request another photograph or officer review. Unreadable information is unknown, not absent.

## Contradiction handling

Contradictions include different values for the same declaration across photographs, disagreement between OCR observations, disagreement between a machine observation and visible package text, and conflicting advisory context suggestions. A contradiction must preserve all source observations and evidence references, surface `REVIEW_REQUIRED`, and prevent review confirmation from remaining current after a correction.

An officer correction is an append-only overlay: it records the original machine-observed declaration, the officer-confirmed visible value, the supporting capture, the reason, the officer identity, and the time. Repeated corrections must retain the same original machine observation and every correction record. A correction may confirm visible text only; it cannot create a `NOT_DETECTED` legal absence and cannot promote Gemini or any `AI_OBSERVED` value into the authoritative candidate set. Deterministic assessment must rerun after the correction.

## Rule-specific evidence

Surface coverage and general image quality are necessary but not sufficient. Each evaluated rule needs evidence tied to the declaration and location that the rule governs:

- Legal Metrology identity, net quantity, MRP, unit sale price, month/year, business-party, country-of-origin, consumer-care, and applicable QR-instruction checks require declaration-specific captures and visible text evidence.
- Rule 7, Rule 8, and Rule 9 visual checks require the relevant declaration region, its package-panel context, and officer-reviewable geometry or readability evidence. Pixel measurements do not establish physical character height without a valid scale reference.
- FSSAI licence, ingredients, allergen, nutrition, vegetarian/non-vegetarian mark, and other applicable food-label checks require food-regime confirmation and evidence for the specific label element.
- Exemptions and applicability decisions require confirmed package context. Missing or uncertain context produces `REVIEW_REQUIRED` or `NOT_APPLICABLE` only when the deterministic rule explicitly supports that outcome; it never supplies missing visual evidence.

Every PASS, FAIL, review-required result, or future absence result must be traceable to the rule identifier, legal reference, capture identifier, evidence identifier or region, confirmed context, and deterministic reason. Evidence for one rule must not be reused as proof of an unseen declaration required by another rule.

## Decision rule for Stage 1.5

For the active Stage 1.5 plan:

1. Keep `absence_evaluation_eligible=False`.
2. Keep evidence sufficiency at `INSUFFICIENT_FOR_ABSENCE_EVALUATION`, even when all currently requested views are present.
3. Treat missing, unreadable, clipped, contradictory, or unsupported declarations as requiring more evidence or officer review.
4. Permit deterministic PASS or FAIL only where the applicable rule has adequate positive, rule-specific evidence and confirmed context.
5. Require officer confirmation of the current package information after every new photograph or correction.
6. Require explicit officer approval before finalizing the immutable report or opening an external complaint portal. DRISHTI must not submit a complaint automatically.

Changing this boundary requires a later, explicit safety review, new capture-plan coverage, rule-specific tests, and officer-workflow validation. It is not part of Gemini Stage 2.
