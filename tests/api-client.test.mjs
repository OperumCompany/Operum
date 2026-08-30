import test from 'node:test';
import assert from 'node:assert/strict';

import api from '../src/utils/api.ts';

test('deduplicates only identical GET requests that are still in flight', async () => {
  const originalFetch = globalThis.fetch;
  const originalLocalStorage = globalThis.localStorage;
  let fetchCount = 0;
  let releaseFirstRequest;

  globalThis.localStorage = {
    getItem: () => null,
  };
  globalThis.fetch = async () => {
    fetchCount += 1;
    if (fetchCount === 1) {
      await new Promise((resolve) => { releaseFirstRequest = resolve; });
    }
    return new Response(JSON.stringify({ request: fetchCount }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  try {
    const first = api.get('/dashboard-data');
    const duplicate = api.get('/dashboard-data');
    await Promise.resolve();

    assert.equal(fetchCount, 1);
    releaseFirstRequest();
    assert.deepEqual(await Promise.all([first, duplicate]), [{ request: 1 }, { request: 1 }]);

    assert.deepEqual(await api.get('/dashboard-data'), { request: 2 });
    assert.equal(fetchCount, 2);
  } finally {
    globalThis.fetch = originalFetch;
    if (originalLocalStorage === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = originalLocalStorage;
  }
});

test('does not reuse an in-flight GET after a mutation starts', async () => {
  const originalFetch = globalThis.fetch;
  const originalLocalStorage = globalThis.localStorage;
  let getCount = 0;
  let releaseStaleRequest;

  globalThis.localStorage = { getItem: () => null };
  globalThis.fetch = async (_url, options = {}) => {
    if ((options.method ?? 'GET') === 'POST') {
      return new Response(JSON.stringify({ saved: true }), { status: 200 });
    }
    getCount += 1;
    const requestNumber = getCount;
    if (requestNumber === 1) {
      await new Promise((resolve) => { releaseStaleRequest = resolve; });
    }
    return new Response(JSON.stringify({ request: requestNumber }), { status: 200 });
  };

  try {
    const stale = api.get('/portfolio');
    await Promise.resolve();
    await api.post('/portfolio', { name: 'Atualizada' });
    const fresh = api.get('/portfolio');
    await Promise.resolve();

    assert.equal(getCount, 2);
    assert.deepEqual(await fresh, { request: 2 });
    releaseStaleRequest();
    assert.deepEqual(await stale, { request: 1 });
  } finally {
    globalThis.fetch = originalFetch;
    if (originalLocalStorage === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = originalLocalStorage;
  }
});
