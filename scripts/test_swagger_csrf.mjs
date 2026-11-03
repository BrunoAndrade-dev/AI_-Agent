// Exercise the actual template function without a browser or private credentials.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const source = readFileSync(
  new URL('../backend/apps/core/templates/core/swagger_ui.js', import.meta.url), 'utf8'
).split('{% include')[0]
  .replace('{{ csrf_header_name|escapejs }}', 'X-CSRFTOKEN')
  .replace('{{ csrf_cookie_name|escapejs }}', 'csrftoken');
const manual = 'm'.repeat(64);
const initial = 'a'.repeat(32);
const rotated = 'b'.repeat(32);
const document = { cookie: `csrftoken=${initial}` };
const context = {
  Headers, URL, document,
  window: { location: { href: 'http://localhost:8000/api/docs/', origin: 'http://localhost:8000' } },
  requestInterceptor(request) {
    request.headers['X-CSRFTOKEN'] = manual;
    return request;
  },
};
runInNewContext(source, context);
const request = (extra = {}) => ({
  url: 'http://localhost:8000/api/chat/session/', method: 'POST',
  headers: { 'X-CSRFToken': manual, Authorization: 'example' }, ...extra,
});

const duplicate = new Headers({ 'X-CSRFToken': initial, 'X-CSRFTOKEN': manual });
assert(duplicate.get('X-CSRFToken').includes(','), 'Reproduce the duplicate-header bug');
let result = context.currentCsrfRequest(request());
assert.equal(result.headers['x-csrftoken'], initial);
assert.equal(Object.keys(result.headers).filter(key => key.toLowerCase() === 'x-csrftoken').length, 1);
assert.equal(result.headers.authorization, 'example');
document.cookie = `other=value; csrftoken=${rotated}`;
result = context.currentCsrfRequest(request());
assert.equal(result.headers['x-csrftoken'], rotated, 'Read the renewed cookie after login');
result = context.currentCsrfRequest(request({ url: 'https://external.example/path' }));
assert.equal(result.headers['x-csrftoken'], undefined, 'Never send CSRF to another origin');
result = context.currentCsrfRequest(request({ method: 'GET' }));
assert.equal(result.headers['x-csrftoken'], undefined);
document.cookie = '';
result = context.currentCsrfRequest(request());
assert.equal(result.headers['x-csrftoken'], manual, 'Support a manually supplied token');
result = context.currentCsrfRequest(request({ headers: {} }));
assert.equal(result.headers['x-csrftoken'], undefined, 'Do not manufacture a missing token');
console.log('Swagger CSRF regression: duplicates, rotation, auth, origin, GET and fallback passed.');
