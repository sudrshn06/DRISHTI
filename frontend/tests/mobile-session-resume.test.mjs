import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  clearSessionState,
  createSessionRevalidator,
  readSessionUser,
  readWorkspaceState,
  saveSessionUser,
  saveWorkspaceState,
} from '../src/services/sessionState.js';

const source = async (path) => readFile(new URL(`../src/${path}`, import.meta.url), 'utf8');

class MemoryStorage {
  constructor() {
    this.values = new Map();
  }

  getItem(key) {
    return this.values.has(key) ? this.values.get(key) : null;
  }

  setItem(key, value) {
    this.values.set(key, String(value));
  }

  removeItem(key) {
    this.values.delete(key);
  }
}

test('session revalidation deduplicates concurrent checks and releases the request slot', async () => {
  let calls = 0;
  let resolveRequest;
  const revalidate = createSessionRevalidator(() => {
    calls += 1;
    return new Promise((resolve) => {
      resolveRequest = resolve;
    });
  }, 100);

  const first = revalidate();
  const second = revalidate();
  assert.strictEqual(first, second);
  await Promise.resolve();
  assert.equal(calls, 1);

  resolveRequest({ username: 'inspector' });
  assert.deepEqual(await first, { username: 'inspector' });

  const third = revalidate();
  await Promise.resolve();
  assert.equal(calls, 2);
  resolveRequest({ username: 'inspector' });
  await third;
});

test('session revalidation timeout settles and permits a later check', async () => {
  let calls = 0;
  const revalidate = createSessionRevalidator(() => {
    calls += 1;
    return new Promise(() => {});
  }, 5);

  await assert.rejects(revalidate(), /timed out/i);
  await assert.rejects(revalidate(), /timed out/i);
  assert.equal(calls, 2);
});

test('session-scoped user and active inspection survive a page reload and can be cleared', () => {
  const storage = new MemoryStorage();
  const user = { username: 'inspector', role: 'INSPECTOR' };
  const workspace = { activeView: 'multi-view', selectedInspectionId: 'inspection-123' };

  saveSessionUser(user, storage);
  saveWorkspaceState(workspace, storage);
  assert.deepEqual(readSessionUser(storage), user);
  assert.deepEqual(readWorkspaceState(storage), workspace);

  clearSessionState(storage);
  assert.equal(readSessionUser(storage), null);
  assert.deepEqual(readWorkspaceState(storage), {
    activeView: 'dashboard',
    selectedInspectionId: null,
  });
});

test('app bootstrap is bounded, silent for cached users, and clears auth only on 401 or 403', async () => {
  const app = await source('App.jsx');
  assert.match(app, /createSessionRevalidator\(getCurrentUser/);
  assert.match(app, /initialAuth\.cachedUser/);
  assert.match(app, /isExplicitAuthRejection/);
  assert.match(app, /\.finally\(\(\) => \{/);
  assert.match(app, /setAuthLoading\(false\)/);
  assert.doesNotMatch(app, /visibilitychange|addEventListener\(['"]focus/);
});

test('active inspection and file selection are preserved across mobile picker resume', async () => {
  const [app, inspection, viewer] = await Promise.all([
    source('App.jsx'),
    source('pages/MultiViewInspection.jsx'),
    source('components/ocr/EvidenceImageViewer.jsx'),
  ]);

  assert.match(app, /readWorkspaceState/);
  assert.match(app, /saveWorkspaceState/);
  assert.match(inspection, /onInspectionStarted\?\.\(result\.inspection_id\)/);
  assert.match(inspection, /event\.target\.value = ''/);
  assert.match(viewer, /event\.target\.value = ''/);
  assert.match(inspection, /type="button"[\s\S]{0,700}Photograph \{requiredViews/);
});
