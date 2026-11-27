// Route-handler tests for app/api/proxy/[...path]/route.ts. A fake API stands in for FastAPI.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import http from 'node:http';
import { createRequire } from 'node:module';
import { afterEach, beforeEach, describe, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const routePath = fileURLToPath(new URL('../app/api/proxy/[...path]/route.ts', import.meta.url));
const require = createRequire(routePath);
const ts = require('typescript');

let api; // the fake API server
let base; // its URL
let route; // the transpiled route module
let respond; // how the fake API answers the current test
let hits; // requests the fake API received
let inits; // the options of each fetch the route made
const realFetch = globalThis.fetch;

function loadRoute(apiUrl) {
  const source = readFileSync(routePath, 'utf8');
  const target = "const FASTAPI_URL = 'http://localhost:8001';";
  // Fail loudly rather than run against the live API if this line ever changes
  assert.ok(source.includes(target), 'FASTAPI_URL line not found in route.ts');
  const { outputText } = ts.transpileModule(source.replace(target, `const FASTAPI_URL = '${apiUrl}';`), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  const compiled = { exports: {} };
  new Function('require', 'module', 'exports', outputText)(require, compiled, compiled.exports);
  return compiled.exports;
}

// A new fake API (and port) per test, so no pooled connection carries over between tests
beforeEach(async () => {
  hits = [];
  inits = [];
  respond = (response) => json(response, 200, {});
  api = http.createServer((request, response) => {
    let body = '';
    request.on('data', (chunk) => (body += chunk));
    request.on('end', () => {
      const hit = { method: request.method, url: request.url, headers: request.headers, body };
      hit.closed = new Promise((resolve) => response.on('close', () => resolve(!response.writableFinished)));
      hits.push(hit);
      respond(response, hit);
    });
  });
  await new Promise((resolve) => api.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${api.address().port}`;
  route = loadRoute(base);
  globalThis.fetch = (url, init) => {
    assert.ok(String(url).startsWith(base + '/'), 'the route tried to reach something other than the fake API');
    inits.push(init);
    return realFetch(url, init);
  };
});

afterEach(() => {
  globalThis.fetch = realFetch;
  api.closeAllConnections();
  api.close();
});

function json(response, status, body, headers = {}) {
  response.writeHead(status, { 'content-type': 'application/json', ...headers });
  response.end(JSON.stringify(body));
}

function call(method, path, { signal, headers, body, search = '' } = {}) {
  const request = {
    method,
    signal: signal ?? new AbortController().signal,
    nextUrl: { search },
    headers: new Headers(headers),
    text: async () => body ?? '',
  };
  return route[method](request, { params: Promise.resolve({ path: path.split('/') }) });
}

const aborted = () => {
  const controller = new AbortController();
  controller.abort();
  return controller.signal;
};

const within = (promise, ms = 3000) => {
  let timer;
  const timeout = new Promise((_, reject) => (timer = setTimeout(() => reject(new Error('timed out')), ms)));
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
};

async function untilCalled(ms = 3000) {
  // The loop keeps its own deadline, so no timers are left running after a failure
  const deadline = Date.now() + ms;
  while (!hits.length) {
    if (Date.now() > deadline) throw new Error('timed out waiting for the fake API to be called');
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
}

describe('normal requests', () => {
  test('forwards path, query, auth and cookie', async () => {
    await call('GET', 'api/projects', {
      search: '?stage=live',
      headers: { authorization: 'Bearer t', cookie: 'apex_token=c', 'x-bot-auth': 'secret' },
    });
    assert.equal(hits[0].url, '/api/projects?stage=live');
    assert.equal(hits[0].headers.authorization, 'Bearer t');
    assert.equal(hits[0].headers.cookie, 'apex_token=c');
    assert.equal(hits[0].headers['x-bot-auth'], undefined);
  });

  test('forwards a POST body', async () => {
    await call('POST', 'api/ideas', { body: '{"title":"i"}' });
    assert.deepEqual([hits[0].method, hits[0].body], ['POST', '{"title":"i"}']);
  });

  for (const method of ['PUT', 'PATCH', 'DELETE']) {
    test(`forwards ${method}`, async () => {
      assert.equal((await call(method, 'api/projects/1')).status, 200);
      assert.equal(hits[0].method, method);
    });
  }

  test('passes status, body and set-cookie back as JSON', async () => {
    respond = (response) => json(response, 404, { detail: 'nope' }, { 'set-cookie': 'apex_token=x; HttpOnly' });
    const result = await call('GET', 'api/missing');
    assert.equal(result.status, 404);
    assert.equal(result.headers.get('content-type'), 'application/json');
    assert.equal(result.headers.get('set-cookie'), 'apex_token=x; HttpOnly');
    assert.deepEqual(await result.json(), { detail: 'nope' });
  });

  for (const method of ['GET', 'POST']) {
    test(`${method}: no abort signal, even if the browser already left`, async () => {
      const result = await within(call(method, 'api/projects', { signal: aborted() }));
      assert.equal(result.status, 200);
      assert.equal('signal' in inits[0], false);
    });

    test(`${method}: a disconnect while waiting does not abort the API call`, async () => {
      let release;
      respond = (response) => (release = () => json(response, 200, { done: true }));
      const browser = new AbortController();
      const pending = call(method, 'api/projects', { signal: browser.signal });
      await untilCalled();
      browser.abort();
      release();
      assert.deepEqual(await (await within(pending)).json(), { done: true });
      assert.equal(await within(hits[0].closed), false);
    });
  }
});

describe('event streams', () => {
  const sse = (response) => {
    response.writeHead(200, { 'content-type': 'text/event-stream; charset=utf-8' });
    response.write(': connected\n\n');
  };

  test('streams the body through as it arrives', async () => {
    let upstream;
    respond = (response) => sse((upstream = response));
    const result = await within(call('GET', 'api/events/stream'));
    assert.equal(result.headers.get('content-type'), 'text/event-stream');
    assert.equal(result.headers.get('cache-control'), 'no-cache, no-transform');
    assert.equal(result.headers.get('x-accel-buffering'), 'no');
    const reader = result.body.getReader();
    const read = async () => new TextDecoder().decode((await within(reader.read())).value);
    assert.equal(await read(), ': connected\n\n');
    upstream.write('data: 1\n\n'); // sent only after the first chunk was read
    assert.equal(await read(), 'data: 1\n\n');
    upstream.end();
    assert.equal((await within(reader.read())).done, true);
  });

  test('a disconnect while streaming closes the API connection', async () => {
    respond = sse;
    const browser = new AbortController();
    await within(call('GET', 'api/events/stream', { signal: browser.signal }));
    browser.abort();
    assert.equal(await within(hits[0].closed), true);
  });

  for (const [name, path, headers] of [
    ['the stream path', 'api/events/stream', {}],
    ['an event-stream Accept header', 'api/other', { accept: 'text/event-stream' }],
  ]) {
    test(`${name}: a disconnect before headers aborts the API call`, async () => {
      respond = () => {}; // never answers
      const browser = new AbortController();
      const pending = call('GET', path, { signal: browser.signal, headers });
      await untilCalled();
      browser.abort();
      assert.equal((await within(pending)).status, 499);
      assert.equal(await within(hits[0].closed), true);
    });
  }

  test('already disconnected: 499 and the API is never called', async () => {
    const result = await within(call('GET', 'api/events/stream', { signal: aborted() }));
    assert.equal(result.status, 499);
    assert.equal(hits.length, 0);
  });

  test('a disconnect while reading a non-stream reply: 499', async () => {
    respond = (response) => {
      response.writeHead(401, { 'content-type': 'application/json' });
      response.write('{');
    };
    const browser = new AbortController();
    const pending = call('GET', 'api/events/stream', { signal: browser.signal });
    await untilCalled();
    setTimeout(() => browser.abort(), 100);
    assert.equal((await within(pending)).status, 499);
  });

  test('an error that is not a disconnect is still thrown', async () => {
    respond = (response) => response.destroy();
    await assert.rejects(within(call('GET', 'api/events/stream')), (error) => error.name !== 'AbortError' && error.message !== 'timed out');
  });
});

describe('known problems', () => {
  test('a 204 reply from the API is passed through', { todo: 'the proxy gives 204 a body, which throws' }, async () => {
    respond = (response) => response.writeHead(204).end();
    assert.equal((await within(call('DELETE', 'api/thing'))).status, 204);
  });
});
