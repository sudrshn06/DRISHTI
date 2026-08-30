# DRISHTI — Current Design System

## 1. Identity

The product name is **DRISHTI**.

The approved descriptor is **Packaged Commodity Inspection Portal** and the tagline is **Every Label Counts**.

The logo combines an inspection frame, eye, packaged commodity, and verification mark. The full approved brand lockup is used where space permits, especially on authentication surfaces; compact logo treatment is used in the authenticated header without recreating or distorting the mark.

## 2. Design character

DRISHTI is a formal, evidence-led government portal. The current visual system uses a white content canvas, navy/teal institutional accents, restrained borders and shadows, readable information density, and explicit regulatory status treatment.

It is not a dark-sidebar SaaS dashboard. It must not use purple glassmorphism, neon glow, 3D/tilt effects, animated background decoration, dramatic text reveals, or playful motion that competes with evidence.

Design priorities:

1. evidence and officer action;
2. readable regulatory hierarchy;
3. unambiguous workflow and status;
4. desktop and mobile reachability;
5. accessible, restrained presentation.

## 3. Application shell and navigation

The authenticated desktop shell uses a white/navy horizontal government-portal header rather than a persistent dark left sidebar. It presents the compact DRISHTI identity, portal descriptor, primary navigation, and current-user controls.

Implemented primary destinations are:

- Dashboard
- Inspect Product
- Inspection History
- Reports
- Rule Library

Reports are accessed through the persisted inspection/history workflow; they are not a separate rule-administration product. On small screens, primary destinations use a reachable bottom navigation treatment and content reserves adequate space so fixed navigation does not cover actions.

Do not document or design Supervisor or Rule Administrator navigation unless those roles and screens are actually implemented.

## 4. Authentication page

The authentication portal uses the full DRISHTI brand asset and a clear sign-in/register form. It should communicate institutional purpose without obscuring the credential task.

Requirements:

- readable label/input pairing;
- visible password and validation errors;
- keyboard and touch accessibility;
- no decorative animation that delays form use;
- brand text remains the approved descriptor/tagline;
- no demo credentials or hardcoded production values.

## 5. Dashboard

The dashboard is a concise operational overview backed by persisted inspection aggregates. Current content includes metric cards, status distribution/summary visualization, and recent inspection access.

Metric cards use restrained navy, green, amber, or red tones according to meaning. Authoritative counts appear immediately and must not animate upward. Dashboard status/counts must reconcile with the backend aggregate and the inspection/report status model.

Finalized is a lifecycle filter/state, not a synonym for compliant. A finalized report may contain review-required or failed findings.

## 6. Inspection workspace

The workspace prioritizes the current capture and the officer's decision path.

Desktop layout:

- primary capture/photos and legal assessment region on the left;
- package information and workflow/detail region on the right;
- presentation/evidence disclosure content spanning the available width where appropriate.

Mobile layout:

- capture and its primary action remain early and reachable;
- package information, legal assessment, and review actions follow in task order;
- fixed navigation must not cover buttons or file/camera controls;
- the camera input requests the rear camera where supported;
- resumed sessions clearly restore the active workspace rather than appearing to discard the photograph.

Advanced evidence, raw OCR, provider audit, and technical metadata belong behind an optional **View details** disclosure. Hiding technical detail by default must never hide a fail, review requirement, required officer action, or the evidence needed to understand a finding.

## 7. Capture presentation

Each capture surface shows:

- requested surface/view;
- captured/pending/upload state;
- quality feedback;
- retry/replace actions where allowed;
- safe image preview through the authenticated API after storage.

Surface labels describe camera perspectives. The UI must not label FRONT as the statutory principal display panel unless the context/evidence explicitly establishes that fact.

Quality feedback should be actionable and neutral: blur, glare, brightness, framing, or unreadable content. It must not imply a legal defect.

## 8. Package information and provider evidence

The officer-facing table aligns each declaration with its current supported value, status, source capture/provider context, and review/correction action.

Presentation rules:

- prefer officer-readable labels over raw schema names;
- keep original machine observation and correction history available;
- distinguish PaddleOCR, Gemini advisory evidence, reconciled candidate, and officer-confirmed value;
- show conflicts as review items rather than silently selecting a value;
- never present AI suggestion as statutory truth;
- keep unsupported inference out of confirmed values;
- describe marketer, manufacturer, packer, and importer roles exactly as captured, without conflation;
- do not derive country of origin from an Indian address.

## 9. Regulatory findings

Finding cards/tables show:

- result badge;
- officer-readable rule title;
- deterministic reason;
- legal reference where available;
- rule-specific evidence link/crop;
- review or clarification action where needed.

Status treatment:

| Status | Presentation intent |
|---|---|
| `PASS` | Green; supported condition passed. |
| `FAIL` | Red; supported deterministic failure. |
| `REVIEW_REQUIRED` | Amber; uncertainty/action required, visually distinct from fail. |
| `NOT_APPLICABLE` | Grey; rule outside confirmed context. |

Do not rely on colour alone. Use text and icons with adequate contrast. Review is not a softer fail and must not be styled as a violation.

## 10. Evidence viewer

The evidence viewer resolves stored images through the authenticated inspection API. Evidence overlays/crops must use coordinates from the same source image.

- Never expose MinIO URLs, keys, or credentials.
- Never draw a bounding box on a different capture from the originating coordinates.
- Use source-aligned crops where coordinates exist.
- If only contextual image evidence exists, show the supporting image without fabricating a bounding box.
- Make raw OCR/provider technical detail optional while keeping necessary evidence accessible.
- Preserve zoom/readability on both phone and desktop.

## 11. History, reports, and rule library

### Inspection History and Reports

History provides persisted inspection access and status-oriented filtering/navigation. Report actions belong to the authorized inspection record. The UI must not show a stale pre-correction snapshot as current and must preserve finalized immutable output.

### Rule Library and legal help

The Rule Library exposes implemented rule/legal reference material. Legal-provision help returns grounded content from the approved corpus or a clear insufficient-support state. Expand/collapse disclosure may be animated subtly, but the content must be immediately accessible and must not look like AI legal authority.

## 12. Report visual language

PDF and DOCX reports are formal inspection records, not alert posters.

The first page emphasizes:

- DRISHTI/report title;
- inspection date and identifier;
- product/category context;
- capture completeness;
- a compact overall disposition;
- reconciled summary counts.

Overall disposition remains clearly visible but uses a compact summary row/badge rather than an oversized coloured banner. Professional status colours are green for compliant, amber for review required, red for non-compliant, and grey for not applicable.

Report tables use officer-readable wording, consistent counts, Unicode-capable fonts, and traceable evidence. The rupee sign (`₹`) and other supported Unicode text must render without console/file-encoding substitution. Presentation must not mutate the stored report snapshot or regulatory meaning.

## 13. Colour and typography

The source stylesheet defines the portal navy family around:

- primary navy: `#163a5f`;
- dark navy: `#102a43`;
- teal/green accents for brand and success;
- slate/grey neutrals for structure and secondary text;
- amber and red reserved for review/failure meaning.

The application font stack is `Noto Sans`, `Segoe UI`, Arial, sans-serif. Typography should remain compact but readable, with clear headings, consistent label/value hierarchy, and no ornamental display fonts.

## 14. Components

### Buttons

- Primary: solid navy with clear verb.
- Secondary: white/neutral with navy or slate border.
- Destructive: red only for genuinely destructive actions.
- Disabled: visibly inactive while retaining readable text.
- Press feedback: restrained scale/colour change, no bounce.

### Cards and panels

- White or very light neutral background.
- Fine border and minimal elevation.
- Clear heading and optional supporting text.
- Hover emphasis only when the entire card is interactive.

### Tables

- Officer-readable column headings.
- Responsive wrapping or stacked mobile representation.
- Status text plus colour/icon.
- No horizontal density that makes primary actions unreachable.

### Disclosures

Use native/accessible disclosure semantics for statutory details, legal help, and technical evidence. The collapsed summary must state what is inside; essential status/actions remain outside.

## 15. Motion

Motion is restrained and must never affect data accuracy or delay usability.

Allowed patterns:

- main page/section reveal: approximately 150–220 ms, opacity plus 4–6 px translation;
- button/card hover: approximately 150–180 ms, slight border/elevation change, no glow;
- accessible disclosure expand/collapse;
- subtle workflow/progress transition;
- brief result-content reveal;
- restrained button press feedback.

Prohibited:

- spotlight/glare effects;
- tilt or 3D cards;
- animated thread/dot-grid backgrounds;
- blur/word-by-word text reveals;
- count-up animation for authoritative metrics;
- motion that obscures, postpones, or changes evidence.

The stylesheet includes a `prefers-reduced-motion: reduce` path. New animation must be disabled or reduced there.

## 16. Responsive and accessibility requirements

- Design touch targets for phone use and gloved/field interaction where practical.
- Maintain visible focus indicators and logical keyboard order.
- Associate form labels and errors programmatically.
- Preserve semantic headings, buttons, links, tables, and disclosures.
- Meet readable contrast without relying on saturated backgrounds.
- Do not convey status by colour alone.
- Prevent sticky/fixed elements from hiding content or primary actions.
- Avoid animation-triggered focus movement.
- Respect reduced-motion preference.

## 17. Presentation integrity

The UI/report layer may translate schema values into officer-readable wording, arrange content, choose compact status styling, and select a valid evidence rendering. It must not:

- change result semantics or counts;
- infer a declaration or legal context;
- make a provider authoritative;
- reinterpret finalized data;
- hide a contradiction, failure, or review requirement;
- hardcode a demonstration outcome;
- alter evidence coordinates to improve appearance.
