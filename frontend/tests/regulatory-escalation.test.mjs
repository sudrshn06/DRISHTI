import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  buildRegulatoryEscalationSummary,
  getConfirmedFailFindings,
  isRegulatoryEscalationAvailable,
} from '../src/services/regulatoryEscalation.js';

const source = async (path) => readFile(new URL(`../src/${path}`, import.meta.url), 'utf8');

const finding = (status, overrides = {}) => ({
  rule_id: `${status}_RULE`,
  field: 'MRP',
  status,
  reason: `${status} deterministic reason`,
  source_reference: `${status} stored legal reference`,
  evidence_ids: [`${status.toLowerCase()}-evidence`],
  capture_ids: ['capture-back'],
  ...overrides,
});

const session = ({ lifecycle = 'FINALIZED', rules = [], food = [], visual = [] } = {}) => ({
  inspection_id: 'inspection-reference-1',
  lifecycle_status: lifecycle,
  rule_evaluations: rules,
  food_label_evaluations: food,
  visual_rule_evaluations: visual,
  aggregated_candidates: [
    { field: 'COMMON_GENERIC_NAME', status: 'DETECTED', raw_value: 'Toor Dal', evidence_ids: [], capture_ids: [] },
    { field: 'BRAND', status: 'DETECTED', raw_value: 'TATA sampann', evidence_ids: [], capture_ids: [] },
    { field: 'MRP', status: 'DETECTED', raw_value: 'MRP ₹90', evidence_ids: ['fail-evidence'], capture_ids: ['capture-back'] },
  ],
  captures: [{ capture_id: 'capture-back', view_id: 'BACK', field_candidates: [] }],
});

test('finalized inspection with at least one deterministic FAIL enables escalation', async () => {
  assert.equal(isRegulatoryEscalationAvailable(session({ rules: [finding('FAIL')] })), true);
  const inspectionPage = await source('pages/MultiViewInspection.jsx');
  assert.match(inspectionPage, /isRegulatoryEscalationAvailable\(session\)/);
  assert.match(inspectionPage, /regulatoryEscalationAvailable && \(/);
  assert.match(inspectionPage, /Report Non-Compliance/);
});

test('finalized inspection with PASS only does not enable escalation', () => {
  assert.equal(isRegulatoryEscalationAvailable(session({ rules: [finding('PASS')] })), false);
});

test('finalized inspection with REVIEW_REQUIRED only does not enable escalation', () => {
  assert.equal(isRegulatoryEscalationAvailable(session({ rules: [finding('REVIEW_REQUIRED')] })), false);
});

test('finalized inspection with NOT_APPLICABLE only does not enable escalation', () => {
  assert.equal(isRegulatoryEscalationAvailable(session({ rules: [finding('NOT_APPLICABLE')] })), false);
});

test('non-finalized inspection with FAIL does not enable escalation', () => {
  assert.equal(isRegulatoryEscalationAvailable(session({ lifecycle: 'READY_FOR_REVIEW', rules: [finding('FAIL')] })), false);
});

test('empty external portal configuration renders the safe configuration message', async () => {
  const page = await source('pages/PrepareCase.jsx');
  assert.match(page, /External complaint portal is not configured\./);
  assert.match(page, /disabled=\{!portalConfigured\}/);
  assert.match(page, /if \(portalConfigured\) setShowPortalConfirmation\(true\)/);
});

test('configured external portal opens only after explicit officer confirmation', async () => {
  const page = await source('pages/PrepareCase.jsx');
  const requestHandler = page.slice(
    page.indexOf('const handleOpenPortalRequest'),
    page.indexOf('const handleConfirmedPortalHandoff'),
  );
  const confirmedHandler = page.slice(
    page.indexOf('const handleConfirmedPortalHandoff'),
    page.indexOf('if (loading)'),
  );
  assert.doesNotMatch(requestHandler, /window\.open/);
  assert.match(requestHandler, /setShowPortalConfirmation\(true\)/);
  assert.match(confirmedHandler, /window\.open\(externalPortalUrl, '_blank', 'noopener,noreferrer'\)/);
  assert.match(page, /showPortalConfirmation &&/);
  assert.match(page, /Confirm and open portal/);
});

test('complaint summary contains only stored deterministic FAIL findings', () => {
  const fail = finding('FAIL');
  const pass = finding('PASS');
  const review = finding('REVIEW_REQUIRED');
  const notApplicable = finding('NOT_APPLICABLE');
  const data = session({ rules: [fail, pass, review, notApplicable] });
  const failures = getConfirmedFailFindings(data);
  const summary = buildRegulatoryEscalationSummary(data);

  assert.equal(failures.length, 1);
  assert.match(summary, /FAIL stored legal reference/);
  assert.match(summary, /FAIL deterministic reason/);
  assert.match(summary, /fail-evidence/);
  assert.match(summary, /MRP ₹90/);
  assert.doesNotMatch(summary, /PASS stored legal reference|PASS deterministic reason/);
  assert.doesNotMatch(summary, /REVIEW_REQUIRED stored legal reference|REVIEW_REQUIRED deterministic reason/);
  assert.doesNotMatch(summary, /NOT_APPLICABLE stored legal reference|NOT_APPLICABLE deterministic reason/);
});
