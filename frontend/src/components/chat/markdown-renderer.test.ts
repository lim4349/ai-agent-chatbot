/**
 * Test suite for XSS protection in markdown renderer
 * This file demonstrates the security features implemented
 */

import { isValidUrlProtocol, fixUrlSpaces, fixListFormatting } from './markdown-renderer';

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
    expect(isValidUrlProtocol(undefined as unknown as string)).toBe(false);
  });
});

describe('fixUrlSpaces', () => {
  test('should fix spaces in domain: "https://www tossinvest. com"', () => {
    const input = '주가는 136.31달러 (출처: https://www tossinvest. com/stocks/US20200930014)';
    const result = fixUrlSpaces(input);
    expect(result).toContain('https://www.tossinvest.com/stocks/US20200930014');
    expect(result).not.toContain('https://www tossinvest. com');
  });

  test('should fix spaces in alphasquare domain', () => {
    const input = 'https://alphasquare co. kr/home/stock-summary';
    const result = fixUrlSpaces(input);
    expect(result).toContain('https://alphasquare.co.kr/home/stock-summary');
  });

  test('should fix spaces in choicestock domain', () => {
    const input = 'https://www choicestock. co. kr/search/summary/PLTR';
    const result = fixUrlSpaces(input);
    expect(result).toContain('https://www.choicestock.co.kr/search/summary/PLTR');
  });

  test('should handle multiple URLs in same text', () => {
    const input = `현재 팔란티어 테크놀로지스(PLTR) 의 주가는 다음과 같습니다- 136.31달러 (출처: https://www tossinvest. com/stocks/US20200930014/order- 142.91달러 (출처: https://alphasquare co. kr/home/stock-summary? code=PLTR- 135.49달러 (애프터마켓 가격, 출처: https://www choicestock. co. kr/search/summary/PLTR`;
    const result = fixUrlSpaces(input);
    expect(result).toContain('https://www.tossinvest.com/stocks/US20200930014');
    expect(result).toContain('https://alphasquare.co.kr/home/stock-summary');
    expect(result).toContain('https://www.choicestock.co.kr/search/summary/PLTR');
  });

  test('should not modify valid URLs', () => {
    const input = 'Visit https://example.com/path?query=1 for more info';
    const result = fixUrlSpaces(input);
    expect(result).toBe(input);
  });

  test('should protect code blocks', () => {
    const input = '```\nhttps://www tossinvest. com\n```';
    const result = fixUrlSpaces(input);
    expect(result).toBe(input);
  });
});

describe('fixListFormatting', () => {
  test('should separate list items with newlines after punctuation', () => {
    const input = '다음과 같습니다- 136.31달러';
    const result = fixListFormatting(input);
    expect(result).toBe('다음과 같습니다\n- 136.31달러');
  });

  test('should separate consecutive list items', () => {
    const input = '- 136.31달러 - 142.91달러';
    const result = fixListFormatting(input);
    expect(result).toContain('\n- 142.91달러');
  });

  test('should not break normal dashes in words', () => {
    const input = 'order-based system';
    const result = fixListFormatting(input);
    expect(result).toBe('order-based system');
  });

  test('should protect code blocks', () => {
    const input = '```\n- item - item\n```';
    const result = fixListFormatting(input);
    expect(result).toBe(input);
  });
});

/**
 * Example malicious inputs that should be blocked:
 *
 * 1. Script injection in markdown:
 *    `\u003cscript\u003ealert('XSS')\u003c/script\u003e`
 *    - Blocked by DOMPurify's FORBID_TAGS configuration
 *
 * 2. Event handler injection:
 *    `\u003cimg src=x onerror="alert('XSS')"\u003e`
 *    - Blocked by DOMPurify's FORBID_ATTR configuration
 *
 * 3. JavaScript links:
 *    `[Click me](javascript:alert('XSS'))`
 *    - Blocked by isValidUrlProtocol() in anchor component
 *
 * 4. Data URLs:
 *    `[Click me](data:text/html,\u003cscript\u003ealert('XSS')\u003c/script\u003e)`
 *    - Blocked by isValidUrlProtocol() in anchor component
 *
 * 5. Iframe injection:
 *    `\u003ciframe src="javascript:alert('XSS')"\u003e\u003c/iframe\u003e`
 *    - Blocked by DOMPurify's FORBID_TAGS configuration
 *
 * 6. Object injection:
 *    `\u003cobject data="javascript:alert('XSS')"\u003e\u003c/object\u003e`
 *    - Blocked by DOMPurify's FORBID_TAGS configuration
 */
