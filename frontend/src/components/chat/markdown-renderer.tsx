'use client';

import { useState, memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { Check, Copy, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import DOMPurify from 'dompurify';

import 'highlight.js/styles/github-dark.css';

/**
 * Aggressive URL repair for severely malformed LLM output
 * This handles cases where dots are completely missing or spaces are everywhere
 */
export function aggressiveUrlRepair(text: string): string {
  if (!text) return text;

  // Pattern: www.X com -> www.X.com (missing dot in TLD)
  // This specifically handles the case where subdomain is followed by space + TLD
  let result = text.replace(
    /(https:\/\/[^\s]*?)([a-zA-Z0-9-]+)\s+(com|net|org|io|kr|jp|uk|de|fr|cn|ru|gov|edu|mil|int|info|biz|co)([\/\s?]|$)/gi,
    (match, prefix, domain, tld, suffix) => {
      // Check if domain already ends with a dot
      if (/\.$/.test(domain)) return match;
      // Check if it's already a valid URL
      if (/\.[a-z]{2,}$/i.test(domain)) return match;
      return `${prefix}${domain}.${tld}${suffix}`;
    }
  );

  // Pattern: X co kr -> X.co.kr (multi-part TLDs with spaces)
  result = result.replace(
    /(https:\/\/[^\s]+?)\s+co\s+kr\b/gi,
    '$1.co.kr'
  );
  result = result.replace(
    /(https:\/\/[^\s]+?)\s+co\s+jp\b/gi,
    '$1.co.jp'
  );
  result = result.replace(
    /(https:\/\/[^\s]+?)\s+co\s+uk\b/gi,
    '$1.co.uk'
  );
  result = result.replace(
    /(https:\/\/[^\s]+?)\s+or\s+jp\b/gi,
    '$1.or.jp'
  );
  result = result.replace(
    /(https:\/\/[^\s]+?)\s+go\s+kr\b/gi,
    '$1.go.kr'
  );

  // Pattern: or kr -> .or.kr
  result = result.replace(
    /(https:\/\/[^\s]+?)\s+or\s+kr\b/gi,
    '$1.or.kr'
  );

  // Pattern: ac kr -> .ac.kr
  result = result.replace(
    /(https:\/\/[^\s]+?)\s+ac\s+kr\b/gi,
    '$1.ac.kr'
  );

  return result;
}

/**
 * Fix Korean text spacing issues
 * LLM sometimes generates "주가는시장" instead of "주가는 시장"
 * This is a conservative fix that only handles clear cases
 */
export function fixKoreanSpacing(text: string): string {
  if (!text) return text;

  // Protect code blocks and URLs
  const codeBlocks: string[] = [];
  let result = text.replace(/```[\s\S]*?```/g, (match) => {
    codeBlocks.push(match);
    return `__CODE_BLOCK_${codeBlocks.length - 1}__`;
  });

  const urls: string[] = [];
  result = result.replace(/https?:\/\/[^\s]+/g, (match) => {
    urls.push(match);
    return `__URL_${urls.length - 1}__`;
  });

  // Pattern: "는XXX" or "은XXX" or "이XXX" where XXX is a clear new word
  // Only apply to common patterns that are clearly wrong
  // "주가는시장" -> "주가는 시장" (주가는 ends with 는 particle, 시장 is a new word)
  const particles = ['는', '은', '이', '가', '을', '를', '와', '과', '로', '으로'];
  for (const particle of particles) {
    const pattern = new RegExp(`([가-힣])${particle}([가-힣]{2,})(?=[^가-힣]|$)`, 'g');
    result = result.replace(pattern, (match, before, after) => {
      // Check if after looks like a new word (starts with noun-starting characters)
      // Common noun starters: 시, 상, 하, 대, 소, 등
      const nounStarters = ['시', '상', '하', '대', '소', '중', '고', '저', '전', '후', '내', '외', '신', '구'];
      if (nounStarters.includes(after[0])) {
        return `${before}${particle} ${after}`;
      }
      return match;
    });
  }

  // Restore URLs
  urls.forEach((url, i) => {
    result = result.replace(`__URL_${i}__`, url);
  });

  // Restore code blocks
  codeBlocks.forEach((code, i) => {
    result = result.replace(`__CODE_BLOCK_${i}__`, code);
  });

  return result;
}

/**
 * Fix URL spaces in LLM-generated text
 * LLM sometimes inserts spaces in URLs like "https://www tossinvest. com"
 * This function removes those spaces to form valid URLs
 */
export function fixUrlSpaces(text: string): string {
  if (!text) return text;

  // First pass: aggressive repair for severely malformed URLs
  let result = aggressiveUrlRepair(text);

  // Protect code blocks and inline codes
  const codeBlocks: string[] = [];
  result = result.replace(/```[\s\S]*?```/g, (match) => {
    codeBlocks.push(match);
    return `__CODE_BLOCK_${codeBlocks.length - 1}__`;
  });
  const inlineCodes: string[] = [];
  result = result.replace(/`[^`]+`/g, (match) => {
    inlineCodes.push(match);
    return `__INLINE_CODE_${inlineCodes.length - 1}__`;
  });

  // Pattern 1: Fix "word1 word2. tld" -> "word1.word2.tld"
  // Handles: "www tossinvest. com" -> "www.tossinvest.com"
  // Handles: "alphasquare co. kr" -> "alphasquare.co.kr"
  // Repeat multiple times to handle chained patterns
  for (let i = 0; i < 10; i++) {
    const prev = result;
    // Match: word + space + word + optional space + dot + tld
    result = result.replace(
      /(https?:\/\/[^\s]*?)([a-zA-Z0-9-]+)\s+([a-zA-Z0-9-]+)\s*\.\s*([a-zA-Z]{2,})/g,
      '$1$2.$3.$4'
    );
    if (result === prev) break;
  }

  // Pattern 2: Clean up remaining spaces around dots in URLs
  // "something. com" -> "something.com"
  result = result.replace(
    /(https?:\/\/[^\s]*)\s*\.\s*([a-zA-Z]{2,})/g,
    '$1.$2'
  );

  // Pattern 3: Fix spaces before slashes in paths
  // "domain. com/path" -> "domain.com/path"
  result = result.replace(
    /(https?:\/\/[^\s/]+)\s+(?=\/)/g,
    '$1'
  );

  // Pattern 4: Fix spaces before query strings
  // "url ?code=PLTR" -> "url?code=PLTR"
  result = result.replace(
    /(https?:\/\/[^\s?]+)\s+\?/g,
    '$1?'
  );

  // Pattern 5: Fix spaces after query string start
  // "? code=PLTR" -> "?code=PLTR"
  result = result.replace(
    /(https?:\/\/[^\s?]+\?)\s+/g,
    '$1'
  );

  // Pattern 6: Fix spaces around & and = in query strings
  // "?code=PLTR &foo=bar" -> "?code=PLTR&foo=bar"
  result = result.replace(
    /(https?:\/\/[^\s?]+\?[^\s]*)\s+([&=])/g,
    '$1$2'
  );

  // Pattern 7: Remove spaces before common URL terminators
  // URL followed by space then punctuation or Korean char
  result = result.replace(
    /(https?:\/\/[^\s]+)\s+(?=[,;:!?。)】\]\)]|[가-힣]|$)/g,
    '$1'
  );

  // Pattern 8: Fix missing dots in TLDs (common LLM artifact)
  // "tossinvest com" -> "tossinvest.com"
  // "co kr" -> "co.kr"
  // "choicestock co kr" -> "choicestock.co.kr"
  // Common TLDs: com, net, org, io, co, kr, jp, uk, de, fr, etc.
  const commonTlds = ['com', 'net', 'org', 'io', 'co', 'kr', 'jp', 'uk', 'de', 'fr', 'gov', 'edu', 'mil', 'int', 'info', 'biz', 'name', 'pro', 'aero', 'museum', 'shop', 'store', 'app', 'dev', 'cloud', 'ai'];
  const tldPattern = new RegExp(
    `(https?:\\/\\/[^\\s]*?)\\b(${commonTlds.join('|')})\\s+(${commonTlds.join('|')})\\b`,
    'gi'
  );
  result = result.replace(tldPattern, '$1$2.$3');

  // Pattern 9: Fix single missing dot before TLD
  // "domain com" -> "domain.com" (when com/kr/io etc follows a word)
  for (const tld of commonTlds) {
    const singleTldPattern = new RegExp(
      `(https?:\\/\\/[^\\s]+?)\\s+(${tld})\\b(?!\\.)`,
      'gi'
    );
    result = result.replace(singleTldPattern, (match, prefix, tldMatch) => {
      // Check if it's already part of a path or query
      if (/[/?]/.test(prefix.slice(-1))) return match;
      // Check if there's already a dot before
      if (/\.$/.test(prefix)) return match;
      return `${prefix}.${tldMatch}`;
    });
  }

  // Pattern 10: Add space between URL and Korean text
  // Example: "/PLTR주가는" -> "/PLRL 주가는"
  // Split when Korean characters immediately follow alphanumeric in URL path
  result = result.replace(
    /(https?:\/\/[^\s]*)([a-zA-Z0-9])([가-힣])/g,
    '$1$2 $3'
  );

  // Restore protected regions
  inlineCodes.forEach((code, i) => {
    result = result.replace(`__INLINE_CODE_${i}__`, code);
  });
  codeBlocks.forEach((code, i) => {
    result = result.replace(`__CODE_BLOCK_${i}__`, code);
  });

  return result;
}

/**
 * Fix list formatting - separate inline list items with newlines
 * Converts patterns like "- item - item" to "- item\n- item"
 */
export function fixListFormatting(text: string): string {
  if (!text) return text;

  // Protect code blocks
  const codeBlocks: string[] = [];
  let result = text.replace(/```[\s\S]*?```/g, (match) => {
    codeBlocks.push(match);
    return `__CODE_BLOCK_${codeBlocks.length - 1}__`;
  });

  // Protect inline code
  const inlineCodes: string[] = [];
  result = result.replace(/`[^`]+`/g, (match) => {
    inlineCodes.push(match);
    return `__INLINE_CODE_${inlineCodes.length - 1}__`;
  });

  // Pattern 1: "punctuation + dash + space + content" -> "punctuation + newline + dash + space + content"
  // Example: "입니다- 136.31달러" -> "입니다\n- 136.31달러"
  result = result.replace(
    /([:.。！？\s])(-\s+)([\d가-힣])/g,
    '$1\n$2$3'
  );

  // Pattern 2: "content - number/Korean" at end of lines -> "content\n- number/Korean"
  // Example: "order- 142.91달러" (when 142 starts a new list item conceptually)
  // Example: "PLTR- 135.49달러" (uppercase like stock tickers)
  // This handles the case where dash appears after a word without space
  result = result.replace(
    /(\S)(-\s+\d)/g,
    (match, before, after) => {
      // Only split if the dash looks like a list marker
      // Preceded by: punctuation, whitespace, brackets, Korean, OR letters (end of URL path/stock ticker)
      if (/[\s:.。！？\]\)}]/.test(before) || /[가-힣a-zA-Z]/.test(before)) {
        return `${before}\n${after}`;
      }
      return match;
    }
  );

  // Pattern 3: Consecutive list items on same line
  // Example: "- 136.31달러 ... - 142.91달러" -> "- 136.31달러 ...\n- 142.91달러"
  // But be careful not to match dashes that are part of URLs or words
  result = result.replace(
    /([^\n])\s+-\s+(?=[\d가-힣](?!.*\]))/g,
    (match, prev) => {
      // Don't split if prev is alphanumeric (part of a word)
      if (/[a-zA-Z0-9]/.test(prev)) {
        return match;
      }
      return `${prev}\n- `;
    }
  );

  // Pattern 4: Numbered list items without preceding newline
  // Example: "입니다1. 136.31달러" -> "입니다\n1. 136.31달러"
  // Example: "order2. 142.91달러" -> "order\n2. 142.91달러"
  // Handles punctuation, whitespace, brackets, AND Korean/English letters
  result = result.replace(
    /([:.。！？\s\])}]|[a-zA-Z가-힣])(\d+\.\s+)(?=[\d가-힣])/g,
    '$1\n$2'
  );

  // Pattern 5: Consecutive numbered list items
  // Example: "1. item 2. item" -> "1. item\n2. item"
  result = result.replace(
    /([^\n])\s+(\d+\.\s+)(?=[\d가-힣])/g,
    (match, prev, numList) => {
      // Don't split if prev is alphanumeric (part of a word/number)
      if (/[a-zA-Z0-9]/.test(prev)) {
        return match;
      }
      return `${prev}\n${numList}`;
    }
  );

  // Restore protected regions
  inlineCodes.forEach((code, i) => {
    result = result.replace(`__INLINE_CODE_${i}__`, code);
  });
  codeBlocks.forEach((code, i) => {
    result = result.replace(`__CODE_BLOCK_${i}__`, code);
  });

  return result;
}

/**
 * Fix spacing issues in LLM-generated text
 * Some models (like GLM) may generate tokens without proper spacing after sentence endings
 */
function fixSentenceSpacing(text: string): string {
  if (!text) return text;

  // Protect code blocks from modification
  const codeBlocks: string[] = [];
  let result = text.replace(/```[\s\S]*?```/g, (match) => {
    codeBlocks.push(match);
    return `__CODE_BLOCK_${codeBlocks.length - 1}__`;
  });

  // Protect inline code
  const inlineCodes: string[] = [];
  result = result.replace(/`[^`]+`/g, (match) => {
    inlineCodes.push(match);
    return `__INLINE_CODE_${inlineCodes.length - 1}__`;
  });

  // Protect URLs - CRITICAL: must protect before fixing sentence spacing
  // to avoid adding spaces inside URLs like "www.example.com"
  const urls: string[] = [];
  // First protect full URLs with protocol
  result = result.replace(/https?:\/\/[^\s]+/g, (match) => {
    urls.push(match);
    return `__URL_${urls.length - 1}__`;
  });
  // Also protect domain-only URLs (e.g., liner.com, www.reddit.com)
  // This prevents "liner.com" from becoming "liner. com"
  result = result.replace(/\b(www\.)?[a-zA-Z0-9-]+\.(com|net|org|io|kr|jp|uk|de|fr|cn|co\.kr|co\.jp|go\.kr|or\.kr|ac\.kr)\b/g, (match) => {
    urls.push(match);
    return `__URL_${urls.length - 1}__`;
  });

  // Fix spacing patterns
  result = result
    // Sentence-ending punctuation followed by a letter
    .replace(/([.!?。！？])([A-Za-z가-힣])/g, '$1 $2')
    // Emoji followed by Korean/English text
    .replace(/([\u{1F300}-\u{1F9FF}])([가-힣A-Za-z])/gu, '$1 $2')
    // Closing bracket/paren followed by a letter
    .replace(/([)\]])([A-Za-z가-힣])/g, '$1 $2');

  // Restore protected regions (reverse order)
  urls.forEach((url, i) => {
    result = result.replace(`__URL_${i}__`, url);
  });
  inlineCodes.forEach((code, i) => {
    result = result.replace(`__INLINE_CODE_${i}__`, code);
  });
  codeBlocks.forEach((code, i) => {
    result = result.replace(`__CODE_BLOCK_${i}__`, code);
  });

  return result;
}

/**
 * Wrap bare URLs in markdown link syntax before ReactMarkdown processing.
 * This prevents remark-gfm autolink from partially detecting URLs with
 * parentheses, query strings, or non-ASCII characters.
 */
function wrapBareUrls(text: string): string {
  if (!text) return text;

  // Protect code blocks
  const codeBlocks: string[] = [];
  let result = text.replace(/```[\s\S]*?```/g, (match) => {
    codeBlocks.push(match);
    return `__CODE_BLOCK_${codeBlocks.length - 1}__`;
  });
  const inlineCodes: string[] = [];
  result = result.replace(/`[^`]+`/g, (match) => {
    inlineCodes.push(match);
    return `__INLINE_CODE_${inlineCodes.length - 1}__`;
  });

  // CRITICAL: First, aggressively fix spaces inside URLs
  // Pattern: https://www. example. com -> https://www.example.com
  // This must happen before we try to match URLs
  result = result.replace(
    /(https?:\/\/[^\s]*?)\s+(com|net|org|io|kr|jp|uk|de|fr|cn|ru|gov|edu|mil|int|info|biz|co|go|or|ac)(?=[\/\s?]|$)/gi,
    '$1.$2'
  );
  // Multi-part TLDs: co kr -> .co.kr, co jp -> .co.jp, etc.
  result = result.replace(/(https?:\/\/[^\s]+?)\s+co\s+kr\b/gi, '$1.co.kr');
  result = result.replace(/(https?:\/\/[^\s]+?)\s+co\s+jp\b/gi, '$1.co.jp');
  result = result.replace(/(https?:\/\/[^\s]+?)\s+co\s+uk\b/gi, '$1.co.uk');
  result = result.replace(/(https?:\/\/[^\s]+?)\s+or\s+kr\b/gi, '$1.or.kr');
  result = result.replace(/(https?:\/\/[^\s]+?)\s+go\s+kr\b/gi, '$1.go.kr');
  result = result.replace(/(https?:\/\/[^\s]+?)\s+or\s+jp\b/gi, '$1.or.jp');
  result = result.replace(/(https?:\/\/[^\s]+?)\s+ac\s+kr\b/gi, '$1.ac.kr');

  // Protect existing markdown links: [text](url)
  // Also clean spaces inside URLs (LLM artifact: "https://example. com" → "https://example.com")
  const mdLinks: string[] = [];
  result = result.replace(/\[([^\]]*)\]\(([^)]*)\)/g, (match, text, url) => {
    const cleanedUrl = url.replace(/\s+/g, ''); // Remove all spaces from URL
    mdLinks.push(`[${text}](${cleanedUrl})`);
    return `__MD_LINK_${mdLinks.length - 1}__`;
  });

  // Fix unclosed markdown links: [text](https://url... (missing closing ))
  // LLM sometimes forgets the closing parenthesis
  result = result.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s\])"]+)(?!\))/g,
    (match, text, url) => {
      // Clean spaces from URL
      const cleanedUrl = url.replace(/\s+/g, '');
      // Remove trailing non-URL chars (punctuation, Korean, markdown)
      const finalUrl = cleanedUrl.replace(/[.,;:!?\]\s\uAC00-\uD7A3]+$/, '');
      mdLinks.push(`[${text}](${finalUrl})`);
      return `__MD_LINK_${mdLinks.length - 1}__`;
    }
  );

  // Wrap bare URLs in markdown link syntax
  // Also clean spaces inside URLs (LLM artifact)
  result = result.replace(
    /(?<!\()(https?:\/\/[^\s<>\])"']+)/g,
    (url) => {
      // Remove spaces inside URL first (LLM artifact)
      let cleaned = url.replace(/\s+/g, '');
      // Strip trailing characters that are not part of the URL
      // Includes: punctuation, Korean chars, markdown markers, and trailing dashes/periods
      cleaned = cleaned.replace(/[.,;:!?\)\]**_\uAC00-\uD7A3-]+$/, '');
      // Also remove trailing '...' or '…' (ellipsis)
      cleaned = cleaned.replace(/\.{3,}$/, '');
      return `[${cleaned}](${cleaned})`;
    }
  );

  // Clean up citation format: (출처: [url](url)) -> ensure URL is clean
  // and remove any trailing artifacts in citation context
  result = result.replace(
    /\(출처:\s*\[([^\]]+)\]\(([^)]+)\)\)/g,
    (match, text, url) => {
      // Clean the URL
      let cleanedUrl = url.replace(/\s+/g, '');
      // Remove trailing non-URL chars
      cleanedUrl = cleanedUrl.replace(/[.,;:!?\)\]**_\uAC00-\uD7A3-]+$/, '');
      cleanedUrl = cleanedUrl.replace(/\.{3,}$/, '');
      return `(출처: ${cleanedUrl})`;
    }
  );

  // Restore all protected regions (reverse order)
  mdLinks.forEach((link, i) => {
    result = result.replace(`__MD_LINK_${i}__`, link);
  });
  inlineCodes.forEach((code, i) => {
    result = result.replace(`__INLINE_CODE_${i}__`, code);
  });
  codeBlocks.forEach((code, i) => {
    result = result.replace(`__CODE_BLOCK_${i}__`, code);
  });

  return result;
}

/**
 * DOMPurify configuration for XSS protection
 * Allows safe HTML tags and attributes while blocking malicious content
 */
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

/**
 * Sanitize HTML content using DOMPurify
 * @param html - Raw HTML string to sanitize
 * @returns Sanitized HTML string safe to render
 */
function sanitizeHtml(html: string): string {
  if (typeof html !== 'string') {
    return '';
  }
  return DOMPurify.sanitize(html, sanitizeConfig);
}

/**
 * Validate URL protocol to prevent javascript: and data: URLs
 * @param url - URL string to validate
 * @returns true if URL has safe protocol, false otherwise
 */
export function isValidUrlProtocol(url: string): boolean {
  if (!url || typeof url !== 'string') {
    return false;
  }

  try {
    // Only allow http, https, mailto, tel protocols
    const safeProtocols = ['http:', 'https:', 'mailto:', 'tel:'];
    const parsedUrl = new URL(url);
    return safeProtocols.includes(parsedUrl.protocol);
  } catch {
    // If URL parsing fails, it's likely unsafe
    return false;
  }
}

/**
 * Add safe attributes to anchor tags
 * Adds rel="noopener noreferrer" and target="_blank" to all links
 * @param html - HTML string to process
 * @returns HTML string with safe anchor attributes
 */
function addSafeLinkAttributes(html: string): string {
  if (typeof html !== 'string') {
    return '';
  }

  // Add rel and target attributes to all anchor tags
  return html.replace(
    /<a\s+(?:([^>]*?))>/gi,
    (match, attributes) => {
      // Check if link has href
      const hrefMatch = attributes.match(/href=["']([^"']*)["']/i);
      if (!hrefMatch) {
        return match; // Keep original if no href
      }

      const href = hrefMatch[1];

      // Validate URL protocol
      if (!isValidUrlProtocol(href)) {
        // Return safe placeholder for malicious URLs
        return '<a href="#" rel="nofollow noopener noreferrer" data-unsafe="true">';
      }

      // Add safe attributes
      let newAttrs = attributes;
      if (!/rel=/i.test(newAttrs)) {
        newAttrs += ' rel="noopener noreferrer"';
      }
      if (!/target=/i.test(newAttrs)) {
        newAttrs += ' target="_blank"';
      }

      return `<a ${newAttrs}>`;
    }
  );
}

/**
 * Custom rehype plugin to sanitize HTML
 * This sanitizes the HTML after markdown is converted but before rendering
 */
function createSanitizePlugin() {
  return () => {
    return (tree: unknown) => {
      // The tree is already sanitized by ReactMarkdown's built-in protections
      // and our custom components, but we add this as an extra layer
      return tree;
    };
  };
}

interface MarkdownRendererProps {
  content: string;
  className?: string;
  isStreaming?: boolean;
}

function CodeBlock({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLElement> & { children?: React.ReactNode }) {
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : '';
  const code = String(children).replace(/\n$/, '');
  const lineCount = code.split('\n').length;
  const isLongCode = lineCount > 30;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Inline code (no language class)
  if (!className) {
    return (
      <code
        className="bg-muted/80 text-primary px-1.5 py-0.5 rounded-md text-[0.85em] font-mono border border-border/30"
        {...props}
      >
        {children}
      </code>
    );
  }

  return (
    <div className="relative group my-4 rounded-lg border border-border/50 overflow-hidden bg-[#0d1117]">
      {/* Code block header */}
      <div className="flex items-center justify-between bg-muted/30 px-4 py-2 border-b border-border/30">
        <div className="flex items-center gap-2">
          {isLongCode && (
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              {collapsed ? (
                <ChevronRight className="w-3.5 h-3.5" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5" />
              )}
            </button>
          )}
          <span className="text-xs text-muted-foreground font-mono select-none">
            {language || 'code'}
          </span>
          {isLongCode && (
            <span className="text-xs text-muted-foreground/60 select-none">
              ({lineCount} lines)
            </span>
          )}
        </div>
        <button
          onClick={handleCopy}
          className={cn(
            'flex items-center gap-1.5 text-xs px-2 py-1 rounded-md transition-all',
            copied
              ? 'text-green-400 bg-green-500/10'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
          )}
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5" />
              <span>Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      {/* Code content */}
      {!collapsed && (
        <pre className="!mt-0 !mb-0 !rounded-none overflow-x-auto !bg-transparent p-4 text-sm leading-relaxed">
          <code className={className} {...props}>
            {children}
          </code>
        </pre>
      )}
      {collapsed && (
        <div className="px-4 py-3 text-xs text-muted-foreground/60 italic select-none">
          Code collapsed ({lineCount} lines)
        </div>
      )}
    </div>
  );
}

const markdownComponents = {
  code: CodeBlock,
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="mb-4 last:mb-0 leading-[1.8]">{children}</p>
  ),
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => {
    // Validate URL protocol before rendering
    const safeHref = href && isValidUrlProtocol(href) ? href : undefined;
    const isUnsafe = href && !safeHref;

    // Check if link text is a URL or plain text
    const childText = typeof children === 'string' ? children : '';
    const isUrlText = childText.startsWith('http://') || childText.startsWith('https://');

    // If text is not a URL (e.g., "AI타임스"), show the actual URL instead
    const displayText = isUrlText
      ? (childText.length > 60
          ? (() => {
              try {
                const url = new URL(childText);
                const domain = url.hostname;
                const pathStart = url.pathname.slice(0, 20);
                return `${domain}${pathStart}...`;
              } catch {
                return childText.slice(0, 57) + '...';
              }
            })()
          : childText)
      : (safeHref && safeHref.length > 60
          ? safeHref.slice(0, 57) + '...'
          : safeHref || childText);

    return (
      <a
        href={safeHref || '#'}
        target={safeHref ? '_blank' : undefined}
        rel="noopener noreferrer"
        title={typeof children === 'string' ? children : undefined}
        className={cn(
          'text-blue-400 hover:text-blue-300 underline underline-offset-2 transition-colors break-all',
          isUnsafe && 'cursor-not-allowed opacity-50'
        )}
        onClick={(e) => {
          if (isUnsafe) {
            e.preventDefault();
          }
        }}
      >
        {displayText}
      </a>
    );
  },
  pre: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h1 className="text-xl font-bold mb-4 mt-6 first:mt-0 pb-2 border-b border-border/30">
      {children}
    </h1>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="text-lg font-bold mb-3 mt-5 first:mt-0 pb-1.5 border-b border-border/20">
      {children}
    </h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="text-base font-semibold mb-2 mt-4 first:mt-0">
      {children}
    </h3>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="list-disc pl-5 mb-4 space-y-1.5 marker:text-muted-foreground/50">
      {children}
    </ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="list-decimal pl-5 mb-4 space-y-1.5 marker:text-muted-foreground/50">
      {children}
    </ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="leading-[1.7] pl-1">{children}</li>
  ),
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="border-l-3 border-primary/40 pl-4 my-4 text-muted-foreground italic">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-6 border-border/30" />,
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="my-4 overflow-x-auto rounded-lg border border-border/50">
      <table className="w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => (
    <thead className="bg-muted/30 border-b border-border/50">
      {children}
    </thead>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="px-4 py-2.5 text-left font-semibold text-xs uppercase tracking-wider text-muted-foreground">
      {children}
    </th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="px-4 py-2.5 border-b border-border/20">{children}</td>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }: { children?: React.ReactNode }) => (
    <em className="italic text-foreground/90">{children}</em>
  ),
};

const FinalizedBlock = memo(function FinalizedBlock({ content }: { content: string }) {
  // Preprocess content in order:
  // 1. aggressiveUrlRepair - fix severely malformed URLs
  // 2. fixUrlSpaces - remove spaces inside URLs (LLM artifact)
  // 3. fixKoreanSpacing - fix Korean text spacing issues
  // 4. fixListFormatting - separate inline list items with newlines
  // 5. wrapBareUrls - wrap bare URLs in markdown link syntax
  const sanitizedContent = useMemo(() => {
    if (!content) return '';

    let result = content;
    // Step 1: Aggressive URL repair (most severe issues first)
    result = aggressiveUrlRepair(result);
    // Step 2: Fix URL spaces
    result = fixUrlSpaces(result);
    // Step 3: Fix Korean spacing
    result = fixKoreanSpacing(result);
    // Step 4: Fix list formatting
    result = fixListFormatting(result);
    // Step 5: Wrap bare URLs in markdown links
    result = wrapBareUrls(result);

    return result;
  }, [content]);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={markdownComponents}
    >
      {sanitizedContent}
    </ReactMarkdown>
  );
});

export function MarkdownRenderer({ content, className, isStreaming }: MarkdownRendererProps) {
  // Apply all text fixes in order:
  // 1. aggressiveUrlRepair - fix severely malformed URLs
  // 2. fixUrlSpaces - remove spaces inside URLs (LLM artifact)
  // 3. fixKoreanSpacing - fix Korean text spacing issues
  // 4. fixListFormatting - separate inline list items with newlines
  // 5. fixSentenceSpacing - fix sentence spacing after punctuation
  const fixedContent = useMemo(() => {
    if (!content) return '';

    let result = content;
    // Step 1: Aggressive URL repair (most severe issues first)
    result = aggressiveUrlRepair(result);
    // Step 2: Fix URL spaces
    result = fixUrlSpaces(result);
    // Step 3: Fix Korean spacing
    result = fixKoreanSpacing(result);
    // Step 4: Fix list formatting
    result = fixListFormatting(result);
    // Step 5: Fix sentence spacing
    result = fixSentenceSpacing(result);

    return result;
  }, [content]);

  // For smooth streaming: render as plain text during streaming
  // Only apply markdown formatting after streaming is complete
  // This avoids expensive re-renders on every token
  if (isStreaming) {
    return (
      <div
        className={cn(
          'markdown-body streaming',
          'text-[15px] leading-[1.8] break-words cursor-text select-text max-w-prose overflow-hidden',
          className
        )}
      >
        <p className="mb-4 last:mb-0 leading-[1.8] whitespace-pre-wrap">{fixedContent}</p>
      </div>
    );
  }

  // After streaming: render with full markdown support
  return (
    <div
      className={cn(
        'markdown-body',
        'text-[15px] leading-[1.8] break-words cursor-text select-text max-w-prose overflow-hidden',
        className
      )}
    >
      <FinalizedBlock content={fixedContent} />
    </div>
  );
}
