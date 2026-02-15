/**
 * Test suite for XSS protection in markdown renderer
 * This file demonstrates the security features implemented
 */

import { isValidUrlProtocol } from './markdown-renderer';

describe('XSS Protection - URL Validation', () => {
  test('should allow safe HTTP URLs', () => {
    expect(isValidUrlProtocol('http://example.com')).toBe(true);
    expect(isValidUrlProtocol('https://example.com')).toBe(true);
    expect(isValidUrlProtocol('https://example.com/path?query=value')).toBe(true);
  });

  test('should allow safe mailto URLs', () => {
    expect(isValidUrlProtocol('mailto:test@example.com')).toBe(true);
  });

  test('should allow safe tel URLs', () => {
    expect(isValidUrlProtocol('tel:+1234567890')).toBe(true);
  });

  test('should block javascript: URLs', () => {
    expect(isValidUrlProtocol('javascript:alert(1)')).toBe(false);
    expect(isValidUrlProtocol('javascript:void(0)')).toBe(false);
    expect(isValidUrlProtocol('JAVASCRIPT:alert(1)')).toBe(false);
  });

  test('should block data: URLs', () => {
    expect(isValidUrlProtocol('data:text/html,<script>alert(1)</script>')).toBe(false);
  });

  test('should block vbscript: URLs', () => {
    expect(isValidUrlProtocol('vbscript:msgbox(1)')).toBe(false);
  });

  test('should block file: URLs', () => {
    expect(isValidUrlProtocol('file:///etc/passwd')).toBe(false);
  });

  test('should handle invalid URLs gracefully', () => {
    expect(isValidUrlProtocol('')).toBe(false);
    expect(isValidUrlProtocol('not-a-url')).toBe(false);
    expect(isValidUrlProtocol(undefined as any)).toBe(false);
  });
});

/**
 * Example malicious inputs that should be blocked:
 *
 * 1. Script injection in markdown:
 *    `<script>alert('XSS')</script>`
 *    - Blocked by DOMPurify's FORBID_TAGS configuration
 *
 * 2. Event handler injection:
 *    `<img src=x onerror="alert('XSS')">`
 *    - Blocked by DOMPurify's FORBID_ATTR configuration
 *
 * 3. JavaScript links:
 *    `[Click me](javascript:alert('XSS'))`
 *    - Blocked by isValidUrlProtocol() in anchor component
 *
 * 4. Data URLs:
 *    `[Click me](data:text/html,<script>alert('XSS')</script>)`
 *    - Blocked by isValidUrlProtocol() in anchor component
 *
 * 5. Iframe injection:
 *    `<iframe src="javascript:alert('XSS')"></iframe>`
 *    - Blocked by DOMPurify's FORBID_TAGS configuration
 *
 * 6. Object injection:
 *    `<object data="javascript:alert('XSS')"></object>`
 *    - Blocked by DOMPurify's FORBID_TAGS configuration
 */
