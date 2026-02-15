# XSS Protection Implementation

## Overview

This document describes the comprehensive XSS (Cross-Site Scripting) protection implemented in the AI Agent Chatbot frontend's markdown rendering system.

## Security Measures

### 1. DOMPurify Integration

**Location:** `src/components/chat/markdown-renderer.tsx`

DOMPurify is a DOM-only, super-fast, uber-tolerant XSS sanitizer for HTML, MathML and SVG.

**Configuration:**
```typescript
const sanitizeConfig = {
  ALLOWED_TAGS: [
    'p', 'br', 'strong', 'em', 'u', 's', 'code', 'pre',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'blockquote', 'a', 'hr',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'div', 'span', 'del', 'ins', 'sub', 'sup',
  ],
  ALLOWED_ATTR: ['href', 'title', 'class', 'target', 'rel', 'id'],
  ALLOW_DATA_ATTR: false,
  FORBID_TAGS: ['script', 'object', 'embed', 'iframe', 'form', 'input', 'button', 'style'],
  FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onfocus', 'onblur', 'onkeydown', 'onkeyup', 'onsubmit'],
  ALLOW_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
};
```

### 2. URL Protocol Validation

Custom URL validation ensures only safe protocols are allowed in links:

```typescript
function isValidUrlProtocol(url: string): boolean {
  const safeProtocols = ['http:', 'https:', 'mailto:', 'tel:'];
  const parsedUrl = new URL(url);
  return safeProtocols.includes(parsedUrl.protocol);
}
```

**Allowed Protocols:**
- `http:` and `https:` - Standard web protocols
- `mailto:` - Email links
- `tel:` - Telephone links

**Blocked Protocols:**
- `javascript:` - Prevents script execution
- `data:` - Prevents data URL injection
- `vbscript:` - Prevents VBScript execution
- `file:` - Prevents local file access
- All other non-standard protocols

### 3. Safe Link Rendering

The anchor component validates URLs before rendering:

```typescript
const safeHref = href && isValidUrlProtocol(href) ? href : undefined;
const isUnsafe = href && !safeHref;

return (
  <a
    href={safeHref || '#'}
    target={safeHref ? '_blank' : undefined}
    rel="noopener noreferrer"
    onClick={(e) => {
      if (isUnsafe) {
        e.preventDefault();
      }
    }}
  >
    {children}
  </a>
);
```

**Security Features:**
- Invalid URLs are replaced with `#`
- Unsafe links are visually indicated (opacity 50%, no pointer events)
- All safe links open in new tab with `rel="noopener noreferrer"`
- Click events are prevented for unsafe links

### 4. ReactMarkdown Integration

ReactMarkdown provides built-in XSS protection by:
- Escaping HTML entities by default
- Only rendering markdown, not arbitrary HTML
- Using custom components for additional validation

### 5. Defense in Depth

Multiple layers of security ensure protection:

1. **Input Layer:** ReactMarkdown escapes HTML
2. **Validation Layer:** URL protocol validation
3. **Rendering Layer:** Custom components with safety checks
4. **Output Layer:** DOMPurify sanitization (available for future use)

## Threat Models

### Prevented Attack Vectors

#### 1. Script Injection
**Input:** `<script>alert('XSS')</script>`
**Result:** Script tag is in FORBID_TAGS list, completely removed

#### 2. Event Handler Injection
**Input:** `<img src=x onerror="alert('XSS')">`
**Result:** `onerror` attribute is in FORBID_ATTR list, removed

#### 3. JavaScript Links
**Input:** `[Click me](javascript:alert('XSS'))`
**Result:** Protocol validation fails, link replaced with `#`

#### 4. Data URL Injection
**Input:** `[Click me](data:text/html,<script>alert('XSS')</script>)`
**Result:** Protocol validation fails, link replaced with `#`

#### 5. Iframe Injection
**Input:** `<iframe src="javascript:alert('XSS')"></iframe>`
**Result:** Iframe tag is in FORBID_TAGS list, removed

#### 6. Object Embedding
**Input:** `<object data="javascript:alert('XSS')"></object>`
**Result:** Object tag is in FORBID_TAGS list, removed

#### 7. Form Injection
**Input:** `<form action="javascript:alert('XSS')"><button>Click</button></form>`
**Result:** Form, button, input tags are in FORBID_TAGS list, removed

#### 8. Style Injection
**Input:** `<style>@import 'javascript:alert("XSS")';</style>`
**Result:** Style tag is in FORBID_TAGS list, removed

## Testing

### Manual Testing

Test with these malicious inputs:

```markdown
# Script Injection
<script>alert('XSS')</script>

# Event Handler
<img src=x onerror="alert('XSS')">

# JavaScript Link
[Click](javascript:alert('XSS'))

# Data URL
[Click](data:text/html,<script>alert('XSS')</script>)

# Iframe
<iframe src="javascript:alert('XSS')"></iframe>

# Object
<object data="javascript:alert('XSS')"></object>

# VBScript
<a href="vbscript:msgbox('XSS')">Click</a>

# File Protocol
[Click](file:///etc/passwd)
```

### Expected Behavior

All malicious inputs should be:
- Removed from the rendered output
- Or rendered as harmless text
- Links with unsafe protocols should be unclickable

## Dependencies

- **dompurify**: ^3.3.1 - HTML sanitization
- **@types/dompurify**: ^3.0.5 - TypeScript types
- **react-markdown**: ^10.1.0 - Markdown rendering with built-in XSS protection
- **rehype-highlight**: ^7.0.2 - Code syntax highlighting
- **remark-gfm**: ^4.0.1 - GitHub Flavored Markdown support

## Maintenance

### Keeping DOMPurify Updated

Regularly update DOMPurify to get the latest security patches:

```bash
npm update dompurify
```

### Monitoring for Vulnerabilities

Subscribe to security advisories for:
- DOMPurify
- ReactMarkdown
- Rehype/Remark plugins

### Code Review Checklist

When modifying the markdown renderer:
- [ ] Verify new components validate user input
- [ ] Ensure no new event handlers are allowed
- [ ] Test with XSS payloads
- [ ] Check URL validation logic
- [ ] Update this documentation

## Future Enhancements

### Potential Improvements

1. **Content Security Policy (CSP):** Add CSP headers
2. **Sanitize Function:** Implement `sanitizeHtml()` usage in FinalizedBlock
3. **Rate Limiting:** Add rate limiting for markdown rendering
4. **Input Length Limits:** Enforce maximum content size
5. **Whitelist Domains:** Only allow links to trusted domains
6. **HTML Comments:** Strip HTML comments to prevent information leakage

### Rehype-Sanitize Alternative

Consider using `rehype-sanitize` plugin for additional protection:

```typescript
import rehypeSanitize from 'rehype-sanitize';

<ReactMarkdown
  rehypePlugins={[rehypeHighlight, rehypeSanitize]}
>
  {content}
</ReactMarkdown>
```

## References

- [DOMPurify Documentation](https://github.com/cure53/DOMPurify)
- [ReactMarkdown Security](https://github.com/remarkjs/react-markdown)
- [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [CSP Level 3](https://w3c.github.io/webappsec-csp/)

## License

This security implementation is part of the AI Agent Chatbot frontend project.
