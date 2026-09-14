import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'src');
const source = (name) => fs.readFileSync(path.join(root, name), 'utf8');

test('history search advertises the expanded stored-field coverage', () => {
  const history = source('pages/InspectionHistory.jsx');
  assert.match(history, /Product, brand, business, barcode, reference or status/);
});

test('prior inspections are visibly reference-only and never copied', () => {
  const inspection = source('pages/MultiViewInspection.jsx');
  assert.match(inspection, /Previous inspections — reference only/);
  assert.match(inspection, /outcomes, corrections, notes and findings are never copied/);
  assert.match(inspection, /getRelatedInspections/);
  assert.match(inspection, /View historical record/);
});
