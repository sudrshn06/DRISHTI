# DRISHTI — Product Definition

## 1. Product position

DRISHTI is an evidence-first packaged-commodity inspection and decision-support portal for Legal Metrology inspectors. It converts package photographs into traceable machine observations, deterministic regulatory findings, officer-reviewed package information, and an immutable evidence-backed report.

It is not an autonomous enforcement system, legal oracle, general-purpose OCR service, or automatic complaint-submission tool. Machine assistance helps an officer inspect; it does not replace statutory judgment or authorization.

## 2. Problem addressed

Packaged-commodity declarations are distributed across different surfaces, presented in varied typography, and affected by glare, blur, perspective, occlusion, and label layout. Manual inspection must also connect each conclusion to the applicable provision and the exact supporting evidence.

DRISHTI addresses this by keeping capture completeness, image quality, visible declarations, provider provenance, legal applicability, evidence sufficiency, deterministic assessment, officer confirmation, and report finalization as separate, auditable concerns.

## 3. Implemented workflow

```text
Capture package surfaces
  → Validate file and image quality
  → Extract text with PaddleOCR
  → Obtain advisory contextual observations from Gemini when configured
  → Reconcile grounded provider evidence
  → Determine rule applicability and evidence sufficiency
  → Run deterministic Legal Metrology and scoped FSSAI label rules
  → Officer reviews package information and findings
  → Officer finalizes an immutable report snapshot
```

PaddleOCR is the sole OCR engine. Gemini is an advisory contextual-vision provider and cannot assign compliance, invent missing declarations, or override deterministic rules. The authenticated officer remains responsible for final review, finalization, and any external portal handoff.

## 4. Users and access

The implemented roles are:

| Role | Implemented access |
|---|---|
| `INSPECTOR` | Create and manage owned inspections, capture evidence, review package information, correct visible declarations, assess findings, finalize, and obtain reports. |
| `ADMIN` | Administrative user management and broader authorized access, including legal-corpus reindex operations. |

The application does not currently implement separate Supervisor or Rule Administrator roles or their formerly planned screens.

Authentication uses bearer JWTs and Argon2id password hashing. Inspection APIs enforce authenticated access and ownership/administrative authorization.

## 5. Current product capabilities

### Inspection capture

- Create and resume an inspection workspace.
- Capture from a phone camera or select an existing image.
- Require FRONT and BACK under the active plan; accept optional left, right, top, and bottom views.
- Persist a pending mobile photograph in IndexedDB before upload and warn on navigation only when an unstored pending photograph is at risk.
- Restore active inspection/workspace state across ordinary mobile browser interruptions.
- Validate uploaded file type, content, size, image decoding, and integrity hash.
- Evaluate blur, brightness, glare, and related OpenCV quality signals.

`FRONT` is a camera perspective label. It does not, by itself, establish that the image is the statutory principal display panel. Completing FRONT and BACK satisfies the active capture workflow, not full-package legal surface coverage.

### Observation and reconciliation

- Extract OCR text, confidence, and coordinates using PaddleOCR.
- Request contextual package observations from the configured Gemini model when enabled.
- Validate Gemini structured output through strict local Pydantic models.
- Retain provider provenance and conflicts in the audit trail.
- Promote only supported, grounded candidates under the reconciliation policy.
- Preserve PaddleOCR operation when the advisory provider is disabled or fails.
- Block unsupported AI inference from authoritative candidate values.

Advisory-provider degradation is not a hidden replacement engine. PaddleOCR remains the OCR path and no alternate Gemini provider or model is selected automatically.

### Officer review and corrections

- Present candidate package information and evidence to the officer.
- Require current review confirmation before finalization.
- Store corrections as append-only records.
- Preserve the original machine-observed declaration across repeated corrections.
- Invalidate earlier review confirmation after a correction and rerun deterministic assessment.
- Require a supporting capture and officer reason/identity for a correction.
- Prevent a correction from creating legal absence or promoting AI-only values as authoritative facts.

### Regulatory decision support

- Evaluate deterministic Legal Metrology rules.
- Evaluate implemented, scoped FSSAI labelling checks for relevant food-label declarations.
- Keep applicability and evidence sufficiency explicit.
- Emit `PASS`, `FAIL`, `REVIEW_REQUIRED`, or `NOT_APPLICABLE` per evaluated rule.
- Preserve legal reference, deterministic reason, and evidence linkage.
- Provide grounded legal-provision help from an approved local corpus.

DRISHTI does not claim exhaustive coverage of every Legal Metrology or FSSAI provision. A result is limited to the rules, context, captures, and evidence actually evaluated.

### Reporting and audit

- Show dashboard aggregates and inspection history from persisted records.
- Generate structured inspection reports.
- Produce PDF and DOCX reports with evidence references and status counts.
- Produce an evidence package for authorized downstream use.
- Store a finalized immutable report snapshot.
- Prevent an older draft snapshot from replacing a report after correction.
- Resolve capture images through authenticated inspection-authorized endpoints without exposing object-store credentials or direct storage URLs.

Finalization locks the reportable inspection state. It does not mean that all evaluated rules passed, that the product is compliant, or that an enforcement action has been submitted.

## 6. Result meanings

| Result | Meaning |
|---|---|
| `PASS` | The deterministic rule condition passed for the confirmed context and supporting evidence. |
| `FAIL` | The deterministic rule condition failed and the finding is supported by rule-specific evidence. |
| `REVIEW_REQUIRED` | Evidence, context, confidence, provider agreement, or human confirmation is insufficient for a defensible pass/fail conclusion. |
| `NOT_APPLICABLE` | The rule does not apply to the confirmed product/context. This is not a pass. |

Capture/workflow completeness is reported separately from per-rule result. An incomplete capture must not be converted into a legal finding that a declaration is absent.

## 7. Evidence and absence boundary

The active capture plan is configured with `absence_evaluation_eligible=False`.

Therefore:

- no missing declaration may be declared legally absent from the active FRONT/BACK plan;
- OCR non-detection is not proof of absence;
- an officer correction may confirm visible content, but cannot manufacture absence;
- marketer or manufacturer address text does not prove country of origin unless the origin declaration itself is visible and supported;
- evidence from one rule cannot prove a different declaration on an unseen surface;
- contradictions require review until resolved through supported evidence or explicit officer action.

See [6-absence-evaluation-safety.md](6-absence-evaluation-safety.md).

## 8. Supported inspection context

The inspection context records facts such as product category, package type, sale channel, imported status, food status, and other rule inputs. Detected context may be suggested to the officer, but legally significant context must be confirmed rather than silently inferred.

Visual presentation checks are conservative. Pixels alone do not establish physical character height or package dimensions without calibrated scale. Where the implementation cannot support a deterministic measurement, the system requests review instead of inventing one.

## 9. Safety and integrity requirements

- Preserve original image bytes in configured object storage and record integrity metadata.
- Keep storage object keys server-side.
- Commit capture persistence and inspection state atomically; remove the stored object when persistence fails.
- Keep machine observations, reconciliation decisions, officer corrections, findings, and final reports traceable.
- Never fabricate OCR text, provider output, legal citations, evidence, or compliance results.
- Never allow contextual AI to be the legal authority.
- Never submit a complaint or external handoff without explicit officer action.
- Preserve finalized report snapshots as immutable records.

## 10. Current limitations

- The active FRONT/BACK plan is not legally sufficient for absence evaluation.
- Image quality and OCR accuracy depend on capture conditions and label presentation.
- Gemini availability and quota are external service concerns; failure is surfaced explicitly and does not create a second OCR path.
- Physical-size/presentation claims require calibration that ordinary photographs do not provide.
- Regulatory coverage is the implemented rule set, not a certification of all possible obligations.
- The legal-help corpus provides grounded assistance only from approved indexed material and may decline to answer when support is insufficient.

## 11. Success criteria

DRISHTI is successful when an authorized officer can complete a package inspection with:

1. durable, authorized evidence capture;
2. visible provider provenance and quality limitations;
3. supported package-information candidates;
4. deterministic, cited rule outcomes;
5. explicit review where evidence is insufficient or contradictory;
6. officer-controlled correction and finalization; and
7. a consistent, immutable, evidence-backed report.
