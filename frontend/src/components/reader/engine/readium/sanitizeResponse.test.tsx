import { sanitizeResponse } from '@/components/reader/engine/readium/sanitizeResponse.ts';
import { expect, test } from 'vitest';

const A_HOSTILE_CHAPTER = `<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>On Attention</title>
    <script>parent.document.body.setAttribute('data-pwned', 'inline')</script>
    <meta http-equiv="refresh" content="0; url=escape-hatch.xhtml" />
  </head>
  <body onload="parent.document.body.setAttribute('data-pwned', 'onload')">
    <a href="javascript:parent.document.body.setAttribute('data-pwned','href')">A link.</a>
  </body>
</html>`;

const sanitizedText = async (body: string, contentType: string, status = 200) => {
  const response = await sanitizeResponse(
    new Response(body, { status, headers: { 'Content-Type': contentType } })
  );
  return response.text();
};

test('a chapter arrives with no way left to name executable code', async () => {
  const sanitized = await sanitizedText(A_HOSTILE_CHAPTER, 'application/xhtml+xml');

  expect(sanitized).not.toContain('<script');
  expect(sanitized).not.toContain('onload=');
  expect(sanitized).not.toContain('javascript:');
  expect(sanitized).not.toContain('refresh');
});

test('a chapter arrives under a policy that allows only the navigator its scripts', async () => {
  const sanitized = await sanitizedText(A_HOSTILE_CHAPTER, 'application/xhtml+xml');

  const head = new DOMParser().parseFromString(sanitized, 'application/xhtml+xml').head;
  expect(head.firstElementChild?.getAttribute('http-equiv')).toBe('Content-Security-Policy');
  expect(head.firstElementChild?.getAttribute('content')).toBe(
    "script-src blob:; object-src 'none'; child-src 'none'"
  );
});

test('a chapter written without a head still arrives under the policy', async () => {
  const headless = `<html xmlns="http://www.w3.org/1999/xhtml"><body><p>No head.</p></body></html>`;

  const sanitized = await sanitizedText(headless, 'application/xhtml+xml');

  const head = new DOMParser().parseFromString(sanitized, 'application/xhtml+xml').head;
  expect(head.firstElementChild?.getAttribute('content')).toBe(
    "script-src blob:; object-src 'none'; child-src 'none'"
  );
});

test('a stylesheet passes through byte-identical', async () => {
  const stylesheet = 'body { margin: 0; }\n/* onload= javascript: */';

  expect(await sanitizedText(stylesheet, 'text/css')).toBe(stylesheet);
});

test('a chapter that does not parse as XHTML is still disarmed and framed as well-formed XHTML', async () => {
  const malformed = A_HOSTILE_CHAPTER.replace('<a href', '<br><a href');

  const sanitized = await sanitizedText(malformed, 'application/xhtml+xml');

  const doc = new DOMParser().parseFromString(sanitized, 'application/xhtml+xml');
  expect(doc.querySelector('parsererror')).toBeNull();
  expect(sanitized).not.toContain('<script');
  expect(sanitized).not.toContain('onload=');
  expect(sanitized).not.toContain('javascript:');
  expect(doc.head.firstElementChild?.getAttribute('http-equiv')).toBe('Content-Security-Policy');
});

test('an HTML chapter naming a parsererror element is still disarmed', async () => {
  const decoy =
    '<html><head><script>alert(1)</script></head><body><parsererror></parsererror></body></html>';

  expect(await sanitizedText(decoy, 'text/html')).not.toContain('<script');
});

test('a chapter the server refused to serve is handed on untouched', async () => {
  expect(await sanitizedText(A_HOSTILE_CHAPTER, 'application/xhtml+xml', 502)).toBe(
    A_HOSTILE_CHAPTER
  );
});
