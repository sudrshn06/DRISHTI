# DRISHTI — Design System

## 1. Visual Identity

### Name

**DRISHTI**

Meaning: "Vision" (Sanskrit) — representing clear-sighted regulatory inspection.

### Design Philosophy

| Attribute | Description |
|-----------|-------------|
| Professional | Government-grade inspection tool, not a consumer app |
| Modern | Clean contemporary design with purposeful interactions |
| Trustworthy | Reliable, authoritative, serious |
| Regulatory | Structured, evidence-oriented, precise |
| Technical | Data-driven, metric-focused |
| Restrained | Premium feel without excess decoration |

### What DRISHTI Looks Like

A serious modern regulatory inspection platform — think government compliance dashboards, audit management tools, or enterprise quality assurance systems.

### What DRISHTI Does NOT Look Like

- Gaming dashboard
- AI demo website
- Cyberpunk interface
- Consumer social app
- Marketing landing page
- Neon-themed dark UI

---

## 2. Application Layout

### Primary Layout Structure

```
┌─────────────────────────────────────────────────────┐
│  Top Bar (Logo, Search, User Menu)                  │
├──────────┬──────────────────────────────────────────┤
│          │                                          │
│  Side    │         Main Content Area                │
│  Nav     │                                          │
│          │                                          │
│          │                                          │
│          │                                          │
│          │                                          │
│          │                                          │
│          │                                          │
├──────────┴──────────────────────────────────────────┤
│  Status Bar (optional — connection status, version) │
└─────────────────────────────────────────────────────┘
```

### Layout Principles

- **Collapsible sidebar** — icon-only mode for more content space.
- **Fixed top bar** — always visible for navigation context.
- **Scrollable main content** — content area scrolls independently.
- **No huge empty hero sections** inside application screens.
- **Content-dense** — maximize information visibility while maintaining readability.

### Login Layout

Full-page centered login form. No sidebar, no top bar. Clean, branded.

---

## 3. Typography

### Font Family

**Inter** — Google Fonts

Clean, highly readable, professional, excellent for data-dense interfaces.

```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

### Type Scale

| Token | Size | Weight | Line Height | Use |
|-------|------|--------|-------------|-----|
| `display-lg` | 30px | 700 | 1.2 | Page titles (Dashboard, Inspections) |
| `display-sm` | 24px | 600 | 1.25 | Section headers |
| `heading-lg` | 20px | 600 | 1.3 | Card titles, modal headers |
| `heading-sm` | 16px | 600 | 1.4 | Sub-section headers |
| `body-lg` | 16px | 400 | 1.5 | Primary body text |
| `body` | 14px | 400 | 1.5 | Standard body text, table cells |
| `body-sm` | 13px | 400 | 1.5 | Secondary text, metadata |
| `caption` | 12px | 400 | 1.4 | Labels, timestamps, captions |
| `overline` | 11px | 600 | 1.4 | Category labels, badge text (uppercase) |
| `mono` | 13px | 400 | 1.5 | Code, evidence IDs, hashes |

### Font Loading

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

---

## 4. Colour Palette

### Design Rationale

DRISHTI uses a muted, professional palette with high-contrast status colors. The palette avoids garish neons and excessive saturation.

### Core Colors

| Token | Hex | HSL | Use |
|-------|-----|-----|-----|
| `primary-50` | `#EFF6FF` | 214 100% 97% | Primary backgrounds |
| `primary-100` | `#DBEAFE` | 214 95% 93% | Primary hover backgrounds |
| `primary-200` | `#BFDBFE` | 214 86% 87% | Primary borders |
| `primary-300` | `#93C5FD` | 214 78% 78% | Primary light accents |
| `primary-400` | `#60A5FA` | 217 72% 68% | Primary accent |
| `primary-500` | `#3B82F6` | 217 91% 60% | **Primary brand** |
| `primary-600` | `#2563EB` | 217 91% 53% | Primary hover |
| `primary-700` | `#1D4ED8` | 224 76% 48% | Primary pressed |
| `primary-800` | `#1E40AF` | 226 71% 40% | Primary dark |
| `primary-900` | `#1E3A8A` | 226 70% 33% | Primary darkest |

### Neutral Colors

| Token | Hex | Use |
|-------|-----|-----|
| `neutral-0` | `#FFFFFF` | White backgrounds |
| `neutral-50` | `#F8FAFC` | Page background |
| `neutral-100` | `#F1F5F9` | Card backgrounds, alternating rows |
| `neutral-200` | `#E2E8F0` | Borders, dividers |
| `neutral-300` | `#CBD5E1` | Disabled borders |
| `neutral-400` | `#94A3B8` | Placeholder text, disabled text |
| `neutral-500` | `#64748B` | Secondary text |
| `neutral-600` | `#475569` | Body text |
| `neutral-700` | `#334155` | Primary text |
| `neutral-800` | `#1E293B` | Headings |
| `neutral-900` | `#0F172A` | Darkest text, sidebar background |

### Status Colors — Compliance Results

| Token | Hex | Use |
|-------|-----|-----|
| `pass-50` | `#F0FDF4` | Pass background |
| `pass-100` | `#DCFCE7` | Pass light |
| `pass-500` | `#22C55E` | **PASS — primary** |
| `pass-600` | `#16A34A` | Pass hover |
| `pass-700` | `#15803D` | Pass text on light bg |
| `fail-50` | `#FEF2F2` | Fail background |
| `fail-100` | `#FEE2E2` | Fail light |
| `fail-500` | `#EF4444` | **FAIL — primary** |
| `fail-600` | `#DC2626` | Fail hover |
| `fail-700` | `#B91C1C` | Fail text on light bg |
| `review-50` | `#FFFBEB` | Review background |
| `review-100` | `#FEF3C7` | Review light |
| `review-500` | `#F59E0B` | **REVIEW — primary** |
| `review-600` | `#D97706` | Review hover |
| `review-700` | `#B45309` | Review text on light bg |
| `incomplete-50` | `#F8FAFC` | Incomplete background |
| `incomplete-100` | `#E2E8F0` | Incomplete light |
| `incomplete-500` | `#94A3B8` | **INCOMPLETE — primary** |
| `error-50` | `#FFF1F2` | System error background |
| `error-500` | `#F43F5E` | **SYSTEM ERROR — primary** |

### Status Color Usage Rules

- PASS / FAIL / REVIEW must be **instantly understandable** at a glance.
- Use status colors consistently across the entire application.
- Status backgrounds should be tinted (50/100 shades), not fully saturated.
- Text on status backgrounds must have sufficient contrast (WCAG AA).
- Do not use status colors for decorative purposes.

> [!IMPORTANT]
> **REVIEW REQUIRED must never be presented visually as FAIL.** REVIEW is an evidence-uncertainty state, not a violation. It must use the amber/review color (`review-500`), not the red/fail color.
>
> **SYSTEM ERROR must never be presented visually as a legal compliance failure.** A system error (e.g., OCR crash, database unavailable, rule engine exception) is a technical failure, not a finding about the product. SYSTEM ERROR uses `error-500` (rose/pink) to visually distinguish it from compliance FAIL (`fail-500` red).
>
> **PACKAGE_TYPE_REVIEW_REQUIRED must be presented as a review/action-needed state**, not as a compliance failure.

---

## 5. Spacing System

### Base Unit: 4px

| Token | Value | Use |
|-------|-------|-----|
| `space-0` | 0px | No spacing |
| `space-1` | 4px | Tight inline spacing |
| `space-2` | 8px | Inline element spacing, icon gaps |
| `space-3` | 12px | Small padding |
| `space-4` | 16px | Standard padding, card padding |
| `space-5` | 20px | Medium padding |
| `space-6` | 24px | Section padding |
| `space-8` | 32px | Large section gaps |
| `space-10` | 40px | Page section margins |
| `space-12` | 48px | Major layout spacing |
| `space-16` | 64px | Page-level spacing |

---

## 6. Border Radius

| Token | Value | Use |
|-------|-------|-----|
| `radius-sm` | 4px | Small elements (badges, tags) |
| `radius-md` | 6px | Inputs, buttons |
| `radius-lg` | 8px | Cards, panels |
| `radius-xl` | 12px | Modals, large containers |
| `radius-2xl` | 16px | Feature cards |
| `radius-full` | 9999px | Avatars, pills |

---

## 7. Shadows

| Token | Value | Use |
|-------|-------|-----|
| `shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle elevation (inputs) |
| `shadow-md` | `0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05)` | Cards |
| `shadow-lg` | `0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04)` | Dropdowns, floating panels |
| `shadow-xl` | `0 20px 25px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04)` | Modals |

---

## 8. Component Library

### 8.1 Buttons

| Variant | Use | Background | Text | Border |
|---------|-----|------------|------|--------|
| **Primary** | Main actions (Create Inspection, Evaluate) | `primary-500` | White | None |
| **Secondary** | Secondary actions (Cancel, Back) | `neutral-0` | `neutral-700` | `neutral-200` |
| **Danger** | Destructive actions (Delete) | `fail-500` | White | None |
| **Ghost** | Tertiary actions (View, Edit) | Transparent | `primary-600` | None |
| **Icon** | Icon-only actions | Transparent | `neutral-500` | None |

**States:** Default → Hover (darken 10%) → Active (darken 15%) → Disabled (opacity 50%) → Loading (spinner)

**Sizes:** `sm` (32px height) | `md` (36px height) | `lg` (40px height)

### 8.2 Forms

**Input Fields:**
- Height: 36px (md), 40px (lg)
- Border: 1px `neutral-200`
- Border radius: `radius-md`
- Focus: 2px ring `primary-500` with 50% opacity
- Error: border `fail-500`, error message below in `fail-700`
- Disabled: background `neutral-100`, text `neutral-400`

**Labels:**
- Font: `body-sm`, weight 500
- Color: `neutral-700`
- Margin bottom: `space-1`

**Select, Textarea:** Same styling as inputs.

### 8.3 Cards

| Variant | Use | Background | Border | Shadow |
|---------|-----|------------|--------|--------|
| **Default** | Standard content card | `neutral-0` | `neutral-200` | `shadow-md` |
| **Inspection** | Inspection summary | `neutral-0` | `neutral-200` + left status bar | `shadow-md` |
| **Metric** | Dashboard KPI | `neutral-0` | `neutral-200` | `shadow-md` |
| **Evidence** | Evidence item | `neutral-50` | `neutral-200` | `shadow-sm` |

**Card Structure:**
```
┌─────────────────────────────────────┐
│  Header (title + actions)           │
├─────────────────────────────────────┤
│  Body (content)                     │
├─────────────────────────────────────┤
│  Footer (metadata, status)          │
└─────────────────────────────────────┘
```

Padding: `space-4` (16px) on all sides. Header/footer separated by 1px `neutral-200` border.

### 8.4 Tables

- Header: `neutral-100` background, `body-sm` font weight 600, `neutral-700` text.
- Rows: alternating `neutral-0` / `neutral-50`.
- Cell padding: `space-3` vertical, `space-4` horizontal.
- Borders: 1px `neutral-200` horizontal dividers.
- Hover: row background `primary-50`.
- Sortable columns: sort icon indicator.
- Pagination: below table, right-aligned.

### 8.5 Navigation

**Sidebar:**
- Width: 240px expanded, 64px collapsed.
- Background: `neutral-900`.
- Text: `neutral-300` (inactive), `neutral-0` (active).
- Active item: `primary-500` left border, `neutral-800` background.
- Icons: Lucide React, 20px.
- Hover: `neutral-800` background.
- Collapse/expand toggle at bottom.

**Top Bar:**
- Height: 56px.
- Background: `neutral-0`.
- Border bottom: 1px `neutral-200`.
- Contains: logo, breadcrumbs, search, notifications, user menu.

**Breadcrumbs:**
- Font: `body-sm`.
- Separator: `/` in `neutral-400`.
- Current page: `neutral-700` (not linked).

---

## 9. Status Components

### 9.1 Status Badges

| Status | Background | Text | Border |
|--------|-----------|------|--------|
| PASS | `pass-100` | `pass-700` | None |
| FAIL | `fail-100` | `fail-700` | None |
| REVIEW | `review-100` | `review-700` | None |
| INCOMPLETE | `incomplete-100` | `neutral-600` | None |
| SYSTEM ERROR | `error-50` | `error-500` | None |
| DRAFT | `neutral-100` | `neutral-600` | None |
| PROCESSING | `primary-100` | `primary-700` | None |
| COMPLETED | `pass-100` | `pass-700` | None |

**Badge Style:** Pill shape (`radius-full`), `caption` font, `overline` letter-spacing, padding `space-1` × `space-3`.

### 9.2 Status Indicators (Inline)

For table cells and list items:
- Colored dot (8px circle) + status text.
- Dot color matches status primary color.

### 9.3 Compliance Result Cards

Large result display on inspection completion:

```
┌────────────────────────────────────┐
│  ● PASS                           │
│  MRP Declaration                   │
│  Rule 6(1)(a) — Present and valid │
│  Confidence: 97%                   │
│  ──────────────────────────────── │
│  Evidence: "MRP ₹50 incl..."      │
│  [View Evidence →]                 │
└────────────────────────────────────┘
```

- Left border: 4px in status color.
- Background: status-50.
- Title: `heading-sm`, status-700.
- Rule citation: `body-sm`, `neutral-500`.
- Evidence link: `primary-600`.

---

## 10. Inspection-Specific Components

### 10.1 Inspection Card (List View)

```
┌─ ✅ ─────────────────────────────────────┐
│  INS-2024-0042                            │
│  Parle-G Biscuits — 200g                  │
│  ────────────────────────────────────── │
│  Inspector: Rajesh Kumar                  │
│  Date: 2024-12-15   Location: Mumbai     │
│  ────────────────────────────────────── │
│  ● PASS: 5   ● FAIL: 1   ● REVIEW: 2    │
└───────────────────────────────────────────┘
```

- Left border: overall compliance status color (4px).
- Hover: slight elevation increase + `primary-50` tint.
- Click: navigate to inspection detail.

### 10.2 Panel Status Visualization

SVG or CSS-based package diagram showing panel states:

```
        ┌─────────┐
        │   TOP   │
        │   ⏳    │
   ┌────┼─────────┼────┐
   │LEFT│  FRONT  │RIGHT│
   │ ✅ │   ✅    │ ❌  │
   └────┼─────────┼────┘
        │  BACK   │
        │   ✅    │
        ├─────────┤
        │ BOTTOM  │
        │   —     │
        └─────────┘
```

Panel state indicators:
- ✅ `PROCESSED` — `pass-500` fill
- 📸 `CAPTURED` — `primary-500` fill
- ⏳ `REQUIRED` — `review-500` fill
- ❌ `RETAKE_REQUIRED` — `fail-500` fill
- — `NOT_REQUIRED` — `neutral-300` fill

### 10.3 Inspection Stepper

Horizontal stepper showing inspection workflow progression:

```
[Product Details] → [Capture Panels] → [Processing] → [Review Results] → [Report]
       ✅                 ●                                                      
```

- Completed steps: `pass-500` icon + text.
- Current step: `primary-500` icon + bold text.
- Future steps: `neutral-400` icon + text.
- Connector lines between steps.

---

## 11. Evidence Components

### 11.1 Evidence Viewer

Full-width image viewer with overlay controls:

```
┌──────────────────────────────────────────┐
│  ┌────────────────────────────────────┐  │
│  │                                    │  │
│  │    Package Image                   │  │
│  │    [MRP ₹50]  ← bounding box      │  │
│  │                                    │  │
│  │    [Manufacturer] ← bounding box   │  │
│  │                                    │  │
│  └────────────────────────────────────┘  │
│  🔍 Zoom: ─────●──── 100%   Panel: FRONT│
├──────────────────────────────────────────┤
│  Evidence List                           │
│  ┌─ MRP ─────────────────── 97% ───┐   │
│  │  "MRP ₹50 incl. of all taxes"   │   │
│  └──────────────────────────────────┘   │
│  ┌─ Manufacturer ──────── 94% ─────┐   │
│  │  "ABC Foods Pvt Ltd"             │   │
│  └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

- Image with pan and zoom (mouse/touch).
- Bounding boxes: 2px `primary-400` outline, `primary-100` semi-transparent fill.
- Active/highlighted box: 2px `primary-600` outline, `primary-200` fill.
- Click evidence item → highlight corresponding bounding box.
- Click bounding box → scroll to evidence item.

### 11.2 Bounding Box Styles

| State | Border | Fill |
|-------|--------|------|
| Default | 2px `primary-400` | `primary-100` @ 30% opacity |
| Hover | 2px `primary-500` | `primary-200` @ 40% opacity |
| Active / Selected | 2px `primary-600` | `primary-200` @ 50% opacity |
| Violation | 2px `fail-500` | `fail-100` @ 30% opacity |

---

## 12. Dashboard Design

### Layout

```
┌──────────────────────────────────────────────────────────┐
│  Dashboard                                    [Date Filter]│
├──────────┬──────────┬──────────┬─────────────────────────┤
│ Total    │ Compliant│ Violations│ Pending Review          │
│  142     │   98     │   31     │   13                    │
│ +12%     │  69%     │  22%     │    9%                   │
├──────────┴──────────┴──────────┴─────────────────────────┤
│                                                          │
│  ┌─ Compliance Trend ─────────────────────────────┐     │
│  │  [Line chart: compliance rate over time]        │     │
│  └─────────────────────────────────────────────────┘     │
│                                                          │
│  ┌─ Violations by Type ──┐  ┌─ Recent Inspections ──┐  │
│  │  [Bar chart]           │  │  [List of 5 recent]    │  │
│  └────────────────────────┘  └────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Metric Cards

- Large number: `display-lg` with CountUp animation (React Bits).
- Percentage change: `caption`, green for positive trend, red for negative.
- Label: `body-sm`, `neutral-500`.
- Background: `neutral-0`.
- Border: `neutral-200`.
- Shadow: `shadow-md`.

### Charts (Recharts)

- Use the DRISHTI color palette.
- Line charts: `primary-500` primary line.
- Bar charts: status colors for compliance states.
- Tooltips: `neutral-0` background, `shadow-lg`.
- Axis labels: `caption`, `neutral-500`.
- Grid: `neutral-100` horizontal grid lines only.

---

## 13. Guided Scanning Design

### Capture Interface

```
┌──────────────────────────────────────────┐
│  Inspection: Parle-G Biscuits            │
│  ═══════════════════════════════════════ │
│  Step 2 of 4: Capture FRONT panel        │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │                                    │  │
│  │      Camera Preview / Drop Zone    │  │
│  │                                    │  │
│  │    📷 Drag & drop or click to      │  │
│  │       upload FRONT panel image     │  │
│  │                                    │  │
│  └────────────────────────────────────┘  │
│                                          │
│  Quality: ──── Checking...               │
│                                          │
│  [← Previous]              [Next →]      │
│                                          │
│  Package Status:                         │
│  FRONT ✅  BACK ⏳  LEFT ⏳  RIGHT —     │
└──────────────────────────────────────────┘
```

- Large drop zone / camera area.
- Step indicator (Stepper component).
- Real-time quality feedback after upload.
- Panel status bar at bottom.
- Clear indication of which panel is being captured.

### Quality Feedback

After image upload, display:

```
✅ Image Quality: ACCEPTABLE
   Blur: OK (score: 245)
   Glare: None detected
   Lighting: Good

───── or ─────

❌ Image Quality: RETAKE REQUIRED
   ⚠ Blur detected (score: 42)
   Recommendation: Hold camera steady, ensure good lighting
   [Retake Photo]
```

---

## 14. Inspection Results Design

### Results Overview

```
┌──────────────────────────────────────────────────────┐
│  Inspection Results                                   │
│  INS-2024-0042 — Parle-G Biscuits 200g               │
│                                                       │
│  Overall: ● 5 PASS  ● 1 FAIL  ● 2 REVIEW            │
│  ═══════════════════════════════════════════════════ │
│                                                       │
│  ┌── FAIL ───────────────────────────────────────┐   │
│  │  Consumer Care Details                         │   │
│  │  Rule 6(1)(f) — Consumer care information      │   │
│  │  not found on any inspected panel.             │   │
│  │  [View Evidence →]                             │   │
│  └────────────────────────────────────────────────┘   │
│                                                       │
│  ┌── REVIEW ─────────────────────────────────────┐   │
│  │  Net Quantity Format                           │   │
│  │  Rule 6(2) — Extracted value "200 gms" may     │   │
│  │  not conform to standard abbreviation.         │   │
│  │  Confidence: 72%                               │   │
│  │  [View Evidence →]                             │   │
│  └────────────────────────────────────────────────┘   │
│                                                       │
│  ┌── PASS ───────────────────────────────────────┐   │
│  │  MRP Declaration                               │   │
│  │  Rule 6(1)(a) — Present and valid.             │   │
│  │  Value: ₹50.00 (incl. all taxes)               │   │
│  │  Confidence: 97%                               │   │
│  │  [View Evidence →]                             │   │
│  └────────────────────────────────────────────────┘   │
│                                                       │
│  [Generate PDF Report]  [Generate DOCX Report]        │
└──────────────────────────────────────────────────────┘
```

- Results sorted: FAIL first, then REVIEW, then PASS.
- Each finding card uses appropriate status color for left border and background.
- "View Evidence" link opens evidence viewer with highlighted bounding box.

---

## 15. Report Preview Design

```
┌──────────────────────────────────────────┐
│  Report Preview                          │
│  ┌────────────────────────────────────┐  │
│  │  ┌──────────────────────────────┐  │  │
│  │  │  INSPECTION REPORT           │  │  │
│  │  │  ─────────────────────────── │  │  │
│  │  │  Reference: INS-2024-0042    │  │  │
│  │  │  Date: 15 Dec 2024           │  │  │
│  │  │  Inspector: Rajesh Kumar     │  │  │
│  │  │  ...                         │  │  │
│  │  └──────────────────────────────┘  │  │
│  └────────────────────────────────────┘  │
│  [⬇ Download PDF]  [⬇ Download DOCX]    │
└──────────────────────────────────────────┘
```

- PDF rendered in-browser via `<iframe>` or PDF viewer.
- Download buttons clearly labeled.

---

## 16. History Screen Design

```
┌──────────────────────────────────────────────────────────┐
│  Inspection History                     [+ New Inspection]│
│  ─────────────────────────────────────────────────────── │
│  Filters: [Status ▼] [Date Range] [Product ▼] [Search 🔍]│
│  ─────────────────────────────────────────────────────── │
│                                                          │
│  ┌─ ● ──────────────────────────────────────────────┐   │
│  │ INS-2024-0042  Parle-G Biscuits  15 Dec 2024     │   │
│  │ ● PASS: 5  ● FAIL: 1  ● REVIEW: 2               │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─ ● ──────────────────────────────────────────────┐   │
│  │ INS-2024-0041  Tata Salt  14 Dec 2024            │   │
│  │ ● PASS: 7  ● FAIL: 0  ● REVIEW: 1               │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  Showing 1–10 of 142          [< 1 2 3 ... 15 >]        │
└──────────────────────────────────────────────────────────┘
```

- Inspection cards with status summary.
- Filtering and search above the list.
- Pagination below.
- AnimatedList for card entrance (React Bits).

---

## 17. Login Screen Design

```
┌──────────────────────────────────────────┐
│                                          │
│                                          │
│           ◆ DRISHTI                      │
│           Legal Metrology                │
│           Inspection Platform            │
│                                          │
│        ┌──────────────────────┐          │
│        │ Username             │          │
│        ├──────────────────────┤          │
│        │ Password             │          │
│        ├──────────────────────┤          │
│        │ [    Sign In       ] │          │
│        └──────────────────────┘          │
│                                          │
│        Department of Consumer Affairs    │
│                                          │
└──────────────────────────────────────────┘
```

- Centered card layout.
- Clean, minimal.
- DRISHTI branding prominent.
- Government/regulatory context visible.
- Background: `neutral-50` or subtle gradient.

---

## 18. Rule Administration Design

```
┌──────────────────────────────────────────────────────────┐
│  Rule Administration                        [+ Add Rule]  │
│  ─────────────────────────────────────────────────────── │
│  ┌──────────────────────────────────────────────────────┐│
│  │ Rule ID  │ Citation     │ Field      │ Eff. From │ ● ││
│  ├──────────┼──────────────┼────────────┼───────────┼───┤│
│  │ RUL-001  │ Rule 6(1)(a) │ mrp        │ 2011-03   │ ✅││
│  │ RUL-002  │ Rule 6(1)(b) │ mfr_name   │ 2011-03   │ ✅││
│  │ RUL-003  │ Rule 6(1)(c) │ net_qty    │ 2017-01   │ ✅││
│  │ RUL-004  │ Rule 5(old)  │ mrp        │ 2011-03   │ ❌││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  Rule Detail (click to expand):                          │
│  ┌──────────────────────────────────────────────────────┐│
│  │ Rule: RUL-001                                        ││
│  │ Citation: Rule 6(1)(a)                               ││
│  │ Title: MRP Declaration Requirement                   ││
│  │ Field: mrp                                           ││
│  │ Validation: presence + format                        ││
│  │ Product Categories: [all]                            ││
│  │ Package Types: [retail, wholesale]                   ││
│  │ Effective: 2011-03-01 → (active)                     ││
│  │ Source: Legal Metrology (PC) Rules, 2011             ││
│  │ Automation: DETERMINISTIC                            ││
│  │ [Edit]  [Deactivate]  [View Versions]                ││
│  └──────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

---

## 19. Loading States

### Full-Page Loading

- Centered spinner + "Loading..." text.
- Spinner: `primary-500` animated ring.
- Background: `neutral-50`.

### Component Loading

- Skeleton placeholder matching component shape.
- Skeleton: `neutral-200` background with shimmer animation.
- Duration: subtle pulse, not distracting.

### Processing States

For OCR / evaluation processing:

```
┌──────────────────────────────────────┐
│  Processing Inspection...             │
│                                      │
│  ◐ Extracting text from FRONT panel  │
│  ✅ Image quality validated           │
│  ⏳ Classifying declarations          │
│  ○ Evaluating compliance             │
│  ○ Generating findings               │
│                                      │
└──────────────────────────────────────┘
```

- Each step updates **only when the backend confirms it** (via polling or WebSocket).
- Anime.js transitions: step icon rotates while processing, checks in on completion.
- **Never fabricate progress.** Each step transitions only on real backend state.
- Classification step uses deterministic methods (regex, pattern matching). No AI step is shown because AI is not part of the mandatory pipeline.
- If a processing step fails, display the specific system error code. Do not convert a system failure into a REVIEW or ambiguous state.

---

## 20. Empty States

### No Inspections

```
┌──────────────────────────────────────┐
│                                      │
│        📋                            │
│        No inspections yet            │
│        Create your first inspection  │
│        to get started.               │
│                                      │
│        [+ New Inspection]            │
│                                      │
└──────────────────────────────────────┘
```

- Centered icon (Lucide React).
- Descriptive text.
- Call-to-action button.
- Light, not alarming.

### No Results (Search/Filter)

```
No inspections match your filters.
[Clear Filters]
```

---

## 21. Error States

### Inline Errors

- Red (`fail-500`) border on input field.
- Error message below field in `fail-700`, `caption` font.

### API Errors

```
┌──────────────────────────────────────┐
│  ⚠ Processing Failed                │
│  OCR engine could not process this   │
│  image. Please try again.            │
│                                      │
│  Error: OCR_PROCESSING_FAILED        │
│                                      │
│  [Retry]  [Back to Inspection]       │
└──────────────────────────────────────┘
```

- Error card: `fail-50` background, `fail-500` left border.
- Error code displayed for support reference.
- Retry button where appropriate.
- Never hide errors.

### System Errors

Full-page error for critical failures:

- Large icon (⚠).
- "Something went wrong" heading.
- Error description.
- Error code.
- [Retry] and [Go to Dashboard] actions.

---

## 22. Responsive Behavior

### Breakpoints

| Breakpoint | Width | Layout |
|-----------|-------|--------|
| `sm` | < 640px | Mobile — single column, no sidebar |
| `md` | 640–1024px | Tablet — collapsible sidebar, 2-column grids |
| `lg` | 1024–1280px | Desktop — expanded sidebar, full layout |
| `xl` | > 1280px | Large desktop — wider content area |

### Responsive Rules

- **Sidebar:** Collapsed to icon-only below `lg`. Hidden below `md` (hamburger menu).
- **Tables:** Horizontal scroll on small screens. Consider card layout for critical tables.
- **Dashboard grid:** 4 columns on `xl`, 2 columns on `md`, 1 column on `sm`.
- **Evidence viewer:** Full-width on mobile with touch gestures.
- **Forms:** Single column on mobile, multi-column on desktop where appropriate.
- **Capture workflow:** Optimized for mobile (scanning is the primary mobile use case).

---

## 23. Accessibility

### Requirements

- **WCAG 2.1 AA** compliance for primary workflows.
- All interactive elements have visible focus indicators (2px `primary-500` outline).
- All images have alt text.
- All form fields have associated labels.
- Status colors are supplemented with text/icons (not color-only).
- PASS ✅, FAIL ❌, REVIEW ⚠ — icon + text + color.
- Minimum contrast ratio 4.5:1 for normal text, 3:1 for large text.
- Keyboard navigation for all interactive elements.
- Screen reader-friendly structure (semantic HTML, ARIA where needed).
- Focus trap in modals.

---

## 24. Anime.js Usage Guide

### Where to Use Anime.js

| Context | Animation | Trigger |
|---------|-----------|---------|
| Panel completion | Panel icon transitions from ⏳ to ✅ | Backend confirms panel processed |
| OCR evidence reveal | Bounding boxes draw in sequentially | Evidence data received from backend |
| Compliance result | Result cards animate in with status color | Evaluation response received |
| PASS/FAIL/REVIEW badge | Scale + fade entrance | Finding rendered |
| Processing pipeline | Step icons transition: ○ → ◐ → ✅ | Backend state updates received |
| Dashboard metrics | CountUp number animation | Dashboard data loaded |
| Report generation | Progress indicator | Backend confirms generation started/complete |
| Page transitions | Fade content in/out | Route change |
| Notification | Slide in from top-right | System event |

### Anime.js Restrictions

1. **All animations must reflect real backend state.** No fake progress.
2. **No gratuitous animation.** Every animation must communicate something useful.
3. **Keep animations short.** 200–400ms for micro-interactions, 500–800ms for major transitions.
4. **Use easing.** `easeOutCubic` for entrances, `easeInCubic` for exits.
5. **Respect `prefers-reduced-motion`.** Reduce or disable animations when user preference is set.
6. **No animation loops** that don't represent actual processing (no infinite spinners for fake activity).

---

## 25. React Bits Usage Guide

### Recommended Components

| Component | Where | Justification |
|-----------|-------|---------------|
| **CountUp** | Dashboard metric cards | Animates real numbers on load |
| **Stepper** | Inspection workflow | Shows inspection progress |
| **AnimatedList** | Inspection history, findings | Smooth list entrance |
| **FadeContent** | Page transitions | Clean content transitions |
| **AnimatedContent** | Panel transitions in guided scan | Smooth panel-to-panel transition |

### NOT Recommended

| Component | Reason |
|-----------|--------|
| Threads | Not relevant to inspection UI |
| DotGrid | Decorative, not informational |
| Shader backgrounds | Decorative, wrong visual tone |
| TiltedCard | Too playful for regulatory tool |
| GlareHover | Too flashy for regulatory tool |
| WebGL decorations | Performance cost, wrong tone |
| Neon effects | Wrong visual identity |
| Particle effects | Wrong visual identity |

---

## 26. Screen Summary

| # | Screen | Primary Users | Key Components |
|---|--------|--------------|----------------|
| 1 | **Login** | All | Login form, branding |
| 2 | **Dashboard** | Inspector, Supervisor | Metric cards, charts, recent inspections |
| 3 | **New Inspection** | Inspector | Product form, category selector |
| 4 | **Product Details** | Inspector | Product info form |
| 5 | **Guided Scan** | Inspector | Panel visualizer, capture interface, quality feedback |
| 6 | **Processing** | Inspector | Pipeline progress, step indicators |
| 7 | **Inspection Result** | Inspector, Supervisor | Findings list (PASS/FAIL/REVIEW), evidence links |
| 8 | **Evidence Viewer** | Inspector, Supervisor | Image viewer, bounding boxes, evidence list |
| 9 | **Violation Details** | Inspector, Supervisor | Finding detail, rule citation, evidence highlight |
| 10 | **Report Preview** | Inspector | PDF viewer, download buttons |
| 11 | **Inspection History** | Inspector, Supervisor | Filterable list, pagination |
| 12 | **Inspection Detail** | Inspector, Supervisor | Full inspection view with all findings and evidence |
| 13 | **Rule Administration** | Rule Admin | Rule table, rule editor, version management |
| 14 | **User Management** | Admin | User table, role assignment |

---

## 27. Icon System

**Lucide React** — consistent, clean, professional icons.

### Key Icons

| Icon | Use |
|------|-----|
| `FileSearch` | Inspection |
| `Camera` | Capture / Scan |
| `CheckCircle` | PASS |
| `XCircle` | FAIL |
| `AlertTriangle` | REVIEW |
| `MinusCircle` | INCOMPLETE |
| `AlertOctagon` | SYSTEM ERROR |
| `LayoutDashboard` | Dashboard |
| `History` | Inspection History |
| `FileText` | Reports |
| `Settings` | Admin / Settings |
| `Users` | User Management |
| `BookOpen` | Rules |
| `Shield` | Legal / Compliance |
| `Eye` | Evidence View |
| `ZoomIn` | Zoom |
| `Upload` | Upload Image |
| `Download` | Download Report |
| `RefreshCw` | Retry |
| `LogOut` | Logout |

Icon size: 20px for navigation and inline, 16px for small contexts, 24px for headers.

---

## 28. Motion and Transition Tokens

| Token | Duration | Easing | Use |
|-------|----------|--------|-----|
| `transition-fast` | 150ms | `ease-out` | Hover states, button feedback |
| `transition-normal` | 250ms | `ease-out` | Component transitions, fade |
| `transition-slow` | 400ms | `ease-in-out` | Page transitions, major state changes |
| `transition-emphasis` | 600ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Result reveal, evidence highlight |

### CSS Custom Properties

```css
:root {
  --transition-fast: 150ms ease-out;
  --transition-normal: 250ms ease-out;
  --transition-slow: 400ms ease-in-out;
  --transition-emphasis: 600ms cubic-bezier(0.16, 1, 0.3, 1);
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --transition-fast: 0ms;
    --transition-normal: 0ms;
    --transition-slow: 0ms;
    --transition-emphasis: 0ms;
  }
}
```
