# DRISHTI — Engineering Rules

These rules protect DRISHTI's evidence integrity, regulatory traceability, and officer-controlled workflow. The implemented application is the reference architecture; changes must remain surgical and must preserve these boundaries.

## 1. Deterministic authority

Deterministic Legal Metrology and scoped FSSAI label rules are the system's compliance authority.

- The same supported evidence and confirmed context must produce the same rule result.
- Rule outcomes are `PASS`, `FAIL`, `REVIEW_REQUIRED`, or `NOT_APPLICABLE`.
- Every fail must identify the deterministic condition, legal/rule reference, and supporting evidence.
- A pass is limited to the evaluated rule and evidence; it is not product certification.
- `NOT_APPLICABLE` must follow confirmed context, not missing data or convenience.
- Insufficient or contradictory evidence must become review, not an invented pass/fail.
- Finalization locks the reviewed record; it does not redefine its compliance result.

No AI output, UI state, report renderer, database lifecycle flag, or external portal may override deterministic rule semantics.

## 2. Evidence-first operation

- Preserve the original capture and its integrity metadata.
- Preserve OCR text, confidence, and coordinates against the correct capture.
- Keep provider observations and reconciliation decisions traceable.
- Use rule-specific evidence; evidence for one declaration cannot prove a different declaration on an unseen surface.
- Keep capture completeness, evidence sufficiency, and rule result separate.
- `FRONT` means camera perspective, not automatically principal display panel.
- Ordinary pixels do not establish physical size without a validated scale/calibration method.
- Never infer a legal absence from OCR non-detection or incomplete surface coverage.
- Keep `absence_evaluation_eligible=False` unless an explicit, separately reviewed change introduces legally sufficient coverage and tests.

## 3. PaddleOCR policy

PaddleOCR is the sole OCR engine.

Prohibited:

- fallback to Tesseract, EasyOCR, browser OCR, cloud OCR, or another hidden engine;
- fabricating text when PaddleOCR fails or returns no usable observation;
- presenting Gemini contextual reading as PaddleOCR output;
- discarding OCR provenance, confidence, or coordinates to simplify downstream code.

An OCR failure must be explicit and retryable where safe. Empty or uncertain OCR must remain an observable state and may require officer review.

## 4. Gemini policy

Gemini is an optional, non-authoritative contextual-vision provider. It may return structured observations from actual package image bytes and may help reconcile visible declarations. Its output must pass strict local Pydantic validation and the hybrid reconciliation policy before any supported candidate is used.

Gemini must not:

- issue `PASS`, `FAIL`, `REVIEW_REQUIRED`, or `NOT_APPLICABLE`;
- invent or interpret law as an authoritative rule;
- infer that a declaration is legally absent;
- promote country of origin from a marketer/manufacturer address;
- fabricate a value, citation, bounding box, or source surface;
- replace officer confirmation;
- trigger automatic complaint submission or external handoff;
- silently switch to another provider or model.

The configured provider/model is deliberate. Do not add a second provider, automatic model switching, or a hidden response-generation path.

## 5. No hidden fallback; safe advisory degradation

“No fallback” prohibits substituting another implementation and presenting its output as if the configured capability succeeded.

Examples of prohibited fallback:

| Failure | Prohibited response |
|---|---|
| PaddleOCR fails | Invoke another OCR engine or manufacture OCR text. |
| Configured Gemini call fails | Switch models/providers or create a fake structured response. |
| Deterministic rule evaluation fails | Ask AI to decide compliance or default to pass. |
| Report generation fails | Return a stale/different report as current. |
| Storage persistence fails | Pretend the capture is durable. |

Safe advisory degradation is different: Gemini is not the OCR or legal authority, so a clear Gemini disabled/error status may leave the valid PaddleOCR evidence path available. The system may continue only within what the remaining supported evidence can justify. It must retain the provider failure, surface conflicts/uncertainty, and produce review when required. This is not provider fallback and must never be described as Gemini success.

## 6. Officer review and corrections

- Officer review must be authenticated, attributable, and current.
- A correction confirms visible evidence; it cannot create a legal absence or unsupported fact.
- Corrections are append-only.
- Repeated corrections retain the same original machine-observed declaration plus every correction record.
- A correction must identify its supporting capture and reason.
- A correction invalidates prior package-information review confirmation and reruns deterministic assessment.
- AI-only values cannot become authoritative merely because an officer correction endpoint exists.
- Finalization requires explicit officer approval and prevents further mutation.
- External portal handoff remains a separate explicit officer action.

## 7. Legal source policy

Use only verified, authoritative material when encoding regulatory rules or populating the approved legal-help corpus.

Acceptable sources include:

- enacted Acts and Rules from official government publications;
- official Gazette notifications and amendments;
- official regulator material appropriate to the implemented scope.

Prohibited:

- inventing legal provisions, thresholds, effective dates, citations, or interpretations;
- treating a blog, vendor summary, or AI answer as statutory authority;
- expanding a rule beyond the wording and context supported by the source;
- presenting legal-help retrieval as a binding legal opinion.

When authoritative support is insufficient, record the uncertainty and require review. Never “complete” the law from memory.

## 8. Applicability and sufficiency

- Evaluate applicability from confirmed context.
- Evaluate evidence sufficiency independently for each rule.
- Do not use capture-plan completion as universal evidence sufficiency.
- Do not use `NOT_APPLICABLE` to hide missing evidence.
- Do not use `PASS` when a required surface, declaration, measurement, or context is unresolved.
- Keep contradictions visible until supported evidence or explicit officer action resolves them.
- Preserve the absence-evaluation boundary in [6-absence-evaluation-safety.md](6-absence-evaluation-safety.md).

## 9. Persistence and report integrity

- Capture object persistence and the capture/inspection database transaction must behave atomically.
- Remove the just-stored object if the corresponding database transaction fails.
- Never expose object-store credentials, direct storage URLs, or server-side object keys to a client.
- Resolve current and legacy stored image keys through authenticated, inspection-authorized APIs.
- Wait for IndexedDB transaction completion before reporting a pending photograph as durably stored.
- Invalidate mutable report state after a correction so an older snapshot cannot be displayed.
- Preserve finalized report snapshots as immutable.
- Keep report status labels, counts, evidence, and rule semantics consistent with the snapshot.
- Presentation-only report changes must not mutate stored regulatory meaning.

## 10. Security and secrets

- Require server-side authentication and authorization for protected data.
- Enforce inspection ownership and Admin privileges at the API boundary.
- Hash passwords with the configured secure password hasher; never store plaintext.
- Keep API keys, JWT secrets, database credentials, storage credentials, and raw authorization headers out of source, client bundles, logs, screenshots, and reports.
- Never print or serialize base64 package images in diagnostics.
- Use explicit credentialed CORS origins; never combine wildcard origins with credentials.
- Do not modify `.env`, insert a live key, or commit secrets as part of an unrelated task.

## 11. API and schema changes

- Verify the currently used route, schema, and persistence path before editing.
- Preserve backward-compatible behavior unless the task explicitly authorizes a contract change.
- Do not invent routes documented nowhere in code.
- Keep provider-facing compatibility schemas separate from strict local/domain validation where required.
- Do not weaken local Pydantic validation to accommodate an external provider.
- Database model changes require a reviewed Alembic migration and corresponding tests.
- Never edit existing inspection data to make a test or demonstration pass.

## 12. Surgical implementation rule

- Diagnose from concrete source, response bodies, logs, or failing tests before changing code.
- Make the smallest change that fixes the proven defect.
- Preserve compatible work already present in a partial working tree.
- Do not mix extraction, legal, storage, report, and presentation changes without explicit scope.
- Keep presentation fixes in presentation layers when regulatory data is already correct.
- Stop and report when the required fix would cross a prohibited boundary.

## 13. Testing and validation

Changes must be verified in proportion to risk.

- Add focused regression coverage for each proven defect.
- Run the affected backend or frontend suite.
- Run frontend lint and production build for frontend changes.
- Run report generation/visual inspection for report-layout changes.
- Run database/object-store/live-provider validation only when those services are in scope and configured.
- Classify PostgreSQL, MinIO, network, quota, and other service failures separately from code failures.
- Never weaken or delete a valid test merely to obtain a green suite.
- Never use fabricated provider output as proof that a live integration works.

## 14. UI and accessibility

- Keep the interface a restrained white/navy government inspection portal.
- Distinguish `REVIEW_REQUIRED` from `FAIL`; do not style uncertainty as guilt.
- Keep authoritative counts static and immediately readable.
- Use subtle motion only where it aids orientation or state change.
- Respect `prefers-reduced-motion` and never delay access to content.
- Keep mobile primary actions reachable and advanced evidence/technical detail optional.
- Do not hardcode demonstration values into production presentation.

## 15. Error and uncertainty policy

Errors must be explicit, safe, and attributable to the correct layer. The system must not transform infrastructure/provider failure into a compliance result.

Examples:

- OCR failure: extraction error, not “declaration absent.”
- Gemini timeout: advisory provider unavailable, not provider agreement.
- Insufficient coverage: review/ineligible absence evaluation, not fail.
- Database failure: transaction failure and object cleanup, not successful capture.
- Report renderer failure: report error, not stale report success.
- Legal corpus has insufficient support: grounded-help refusal, not invented guidance.

Explicit uncertainty is a correct product result when the evidence cannot support more.
