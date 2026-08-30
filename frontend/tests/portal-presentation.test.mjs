import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = async (path) => readFile(new URL(`../src/${path}`, import.meta.url), 'utf8');

test('primary navigation exposes only the five officer portal destinations', async () => {
  const app = await source('App.jsx');
  for (const label of ['Dashboard', 'Inspect Product', 'Inspection History', 'Reports', 'Rule Library']) {
    assert.match(app, new RegExp(`label: '${label}'`));
  }
  assert.doesNotMatch(app, /Advanced Tools|Technical Analysis|SingleImageAnalyzer/);
});

test('internal identifiers are not formatted for display or downloaded filenames', async () => {
  const files = await Promise.all([
    source('App.jsx'), source('pages/Dashboard.jsx'), source('pages/InspectionHistory.jsx'),
    source('pages/MultiViewInspection.jsx'), source('pages/PrepareCase.jsx'), source('services/api.js'),
  ]);
  const presentation = files.join('\n');
  assert.doesNotMatch(presentation, /substring\(0,\s*8\)|Inspection ID:|Case Ref:|Case #|Evidence IDs:/);
  assert.match(presentation, /DRISHTI_Inspection_Report\.pdf/);
  assert.match(presentation, /DRISHTI_Evidence_Package\.zip/);
});

test('dashboard metrics remain bound to authoritative dashboard response fields', async () => {
  const dashboard = await source('pages/Dashboard.jsx');
  assert.match(dashboard, /getDashboardSummary/);
  assert.match(dashboard, /workflow_counts: workflow/);
  assert.match(dashboard, /attention_counts: attention/);
  assert.match(dashboard, /recent_inspections: recent/);
  assert.match(dashboard, /Confirmed non-compliance/);
  assert.match(dashboard, /Needs officer review/);
  assert.match(dashboard, /Additional package evidence required/);
});

test('presentation checks do not expose photograph highlighting controls', async () => {
  const panel = await source('components/ocr/EvidenceInspectorPanel.jsx');
  const presentationSection = panel.slice(
    panel.indexOf('export const PackagePresentationChecks'),
    panel.indexOf('export const EvidenceInspectorPanel'),
  );
  assert.doesNotMatch(presentationSection, /View supporting photograph|onSelectEvidence/);
  assert.match(panel.slice(panel.indexOf('export const EvidenceInspectorPanel')), /View supporting photograph/);
});

test('legal help is officer-facing and finalized context is rendered read-only', async () => {
  const [panel, inspection, api] = await Promise.all([
    source('components/ocr/EvidenceInspectorPanel.jsx'), source('pages/MultiViewInspection.jsx'), source('services/api.js'),
  ]);
  assert.match(panel, /legal-help-button/);
  assert.match(panel, /Retrieving legal guidance/);
  assert.match(panel, /getGroundedExplanation/);
  assert.doesNotMatch(panel, /getGroundedExplanation\(queryText, domainText, '2026-08-27'\)/);
  assert.match(panel, /getVisualPresentationReason/);
  assert.match(api, /api\.post\('\/rag\/explain'/);
  assert.match(inspection, /isFinalized \? \(\s*<div className="mt-3 space-y-3">/);
  assert.match(inspection, /Officer-provided product origin classification/);
});

test('missing optional captures remain neutral and finalized context shows provenance', async () => {
  const inspection = await source('pages/MultiViewInspection.jsx');
  assert.match(inspection, /latestCapture \? <><Lock size=\{12\} \/> Captured · Locked<\/> : 'Not captured'/);
  assert.match(inspection, /Inspection context \{isFinalized && '\(Read-only\)'\}/);
  assert.match(inspection, /Finalized package record is immutable/);
});

test('portal motion is restrained and respects reduced-motion preferences', async () => {
  const [styles, app, panel] = await Promise.all([
    source('index.css'), source('App.jsx'), source('components/ocr/EvidenceInspectorPanel.jsx'),
  ]);
  assert.match(styles, /portal-section-in 190ms ease-out/);
  assert.match(styles, /portal-content-in 180ms ease-out/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(app, /className="portal-view"/);
  assert.match(panel, /portal-result-reveal/);
  assert.doesNotMatch(styles + app, /count-up|spotlight|glare|dot-grid|animated-gradient/i);
});

test('inspection workspace uses balanced columns and a final full-width presentation disclosure', async () => {
  const [inspection, panel, styles] = await Promise.all([
    source('pages/MultiViewInspection.jsx'),
    source('components/ocr/EvidenceInspectorPanel.jsx'),
    source('index.css'),
  ]);
  assert.match(styles, /grid-template-columns: minmax\(0, 1\.4fr\) minmax\(380px, 1fr\)/);
  assert.match(styles, /\.workspace-photographs \{ order: 1; \}/);
  assert.match(styles, /\.workspace-package-information \{ order: 2; \}/);
  assert.match(styles, /\.workspace-assessment \{ order: 3; \}/);
  assert.match(styles, /\.workspace-details \{ order: 4; \}/);
  assert.ok(inspection.indexOf('<PackagePresentationChecks') > inspection.indexOf('workspace-details'));
  assert.match(panel, /const \[isOpen, setIsOpen\] = useState\(false\)/);
  assert.match(panel, /aria-expanded=\{isOpen\}/);
  assert.match(panel, /md:grid-cols-2 xl:grid-cols-3/);
});

test('approved DRISHTI branding appears on login, header and browser icons', async () => {
  const [auth, app, html] = await Promise.all([
    source('components/auth/AuthPortal.jsx'),
    source('App.jsx'),
    readFile(new URL('../index.html', import.meta.url), 'utf8'),
  ]);
  assert.match(auth, /drishti-logo-full\.png/);
  assert.match(auth, /DRISHTI — Packaged Commodity Inspection Portal — Every Label Counts/);
  assert.match(app, /drishti-logo-header\.png/);
  assert.match(app, /drishti-icon\.png/);
  assert.match(app, /alt="DRISHTI"/);
  for (const size of [16, 32, 48, 64]) assert.match(html, new RegExp(`favicon-${size}\\.png`));
  assert.match(html, /DRISHTI — Packaged Commodity Inspection Portal/);
});
