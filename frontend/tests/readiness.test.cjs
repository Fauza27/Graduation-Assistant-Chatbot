/* eslint-disable @typescript-eslint/no-require-imports -- Node test harness loads compiled CommonJS helpers. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

// Exercise the real TS helpers with browser/network boundaries mocked. No
// extra test framework or package installation is needed.
function load(name, overrides = {}, globals = {}) {
  const filename = path.join(__dirname, '..', 'src', 'lib', name + '.ts');
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const loaded = { exports: {} };
  vm.runInNewContext(code, {
    exports: loaded.exports, module: loaded, process,
    require: key => key in overrides ? overrides[key] : require(key),
    ...globals,
  }, { filename });
  return loaded.exports;
}

test('citation uses explicit domain instead of a misleading ID', () => {
  const { resolveCitationUrl } = load('documentSources');
  assert.match(resolveCitationUrl({ domain: 'NON_SKRIPSI', parent_id: 'parent-pi-1' }), /panduan-non-skripsi\.pdf$/);
  assert.match(resolveCitationUrl({ parent_id: 'parent_non_skripsi_2' }), /panduan-non-skripsi\.pdf$/);
  assert.match(resolveCitationUrl({ parent_id: 'ptans-001' }), /panduan-non-skripsi\.pdf$/);
  assert.match(resolveCitationUrl({ source: 'Panduan Penyusunan Penulisan Imliah (PI) Cetak' }), /panduan-pi\.pdf$/);
  assert.equal(resolveCitationUrl({ parent_id: 'unknown-uuid' }), null);
});

test('printed page labels are not used as PDF indices', () => {
  const { resolveCitationUrl } = load('documentSources');
  const url = resolveCitationUrl({ domain: 'PI', title: 'Tahap Pelaksanaan', pages: [7] });
  assert.match(url, /#search=Tahap%20Pelaksanaan$/);
  assert.equal(url.includes('#page=7'), false);
  assert.match(resolveCitationUrl({ domain: 'PI', pages: [7], pdf_pages: [16] }), /#page=16$/);
});

function authFixture() {
  const items = new Map();
  const calls = [];
  const storage = { getItem: k => items.get(k) || null, setItem: (k,v) => items.set(k,v), removeItem: k => items.delete(k) };
  const appStore = { getState: () => ({ clearConversation: () => calls.push('clear-state') }), persist: { clearStorage: () => calls.push('clear-storage') } };
  const fetch = async () => ({ ok: true });
  const auth = load('auth', {
    './store': { useAppStore: appStore },
    './apiConfig': load('apiConfig'),
    './backendAvailability': load('backendAvailability', {}, { fetch, DOMException }),
  }, {
    window: { location: { href: '/chat' } }, localStorage: storage, fetch, AbortSignal,
  });
  const token = (sub, version = 1) => 'e30.' + Buffer.from(JSON.stringify({ sub, version })).toString('base64url') + '.signature';
  return { auth, items, calls, token };
}

test('API paths can use the frontend origin in production', () => {
  const { API_BASE_URL } = load('apiConfig', {}, {
    process: { env: { NEXT_PUBLIC_API_BASE_URL: '/' } },
  });
  assert.equal(API_BASE_URL + '/api/auth/refresh', '/api/auth/refresh');
});

test('research CSV preserves multiline text and neutralizes spreadsheet formulas', () => {
  const { buildResearchCsv } = load('researchReview', { './adminApi': {} });
  const csv = buildResearchCsv([{
    request_id: 'request-1', participant_code: 'P-001', session_code: 'session-1',
    occurred_at: '2026-11-06T01:00:00Z', question: '=SUM(1,2)', answer: 'Jawaban "A"\nBaris kedua',
    sources: [{ title: 'Panduan PI' }], status: 'success', http_status: 200,
    error_source: null, total_ms: 100, email: 'private@example.test',
  }]);
  assert.ok(csv.startsWith('\uFEFF'));
  assert.ok(csv.includes('"\'=SUM(1,2)"'));
  assert.ok(csv.includes('"Jawaban ""A""\nBaris kedua"'));
  assert.ok(!csv.includes('private@example.test'));
});

test('new login and user switch clear cached conversation, same-user refresh preserves it', () => {
  const { auth, calls, token } = authFixture();
  auth.setAuthToken(token('a'));
  assert.deepEqual(calls, ['clear-state', 'clear-storage']);
  calls.length = 0;
  auth.setAuthToken(token('a', 2));
  assert.deepEqual(calls, []);
  auth.setAuthToken(token('b'));
  assert.deepEqual(calls, ['clear-state', 'clear-storage']);
});

test('logout clears token and persisted chat state', () => {
  const { auth, calls, items, token } = authFixture();
  auth.setAuthToken(token('a'));
  calls.length = 0;
  auth.logout();
  assert.equal(items.has('access_token'), false);
  assert.deepEqual(calls, ['clear-state', 'clear-storage']);
});
