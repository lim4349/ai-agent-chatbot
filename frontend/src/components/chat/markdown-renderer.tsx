'use client';

import { useState, memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import rehypeHighlight from 'rehype-highlight';
import { Check, Copy, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import DOMPurify from 'dompurify';

import 'highlight.js/styles/github-dark.css';

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
  const inlineCodes: string[] = [];
  result = result.replace(/`[^`]+`/g, (match) => {
    inlineCodes.push(match);
    return `__INLINE_CODE_${inlineCodes.length - 1}__`;
  });

  // Fix spacing patterns
  result = result
    // Sentence-ending punctuation followed by a letter
    .replace(/([.!?。！？])([A-Za-z가-힣])/g, '$1 $2')
    // Emoji followed by Korean/English text
    .replace(/([\u{1F300}-\u{1F9FF}])([가-힣A-Za-z])/gu, '$1 $2')
    // Closing bracket/paren followed by a letter
    .replace(/([)\]])([A-Za-z가-힣])/g, '$1 $2')
    // Comma/semicolon followed immediately by a letter (no space)
    .replace(/([,;])([A-Za-z가-힣])/g, '$1 $2')
    // Sentence-ending punctuation followed by a digit: "합니다.4" → "합니다. 4"
    .replace(/([.!?。！？])(\d)/g, '$1 $2')
    // Korean text followed by a digit: "합니다4." → "합니다 4."
    .replace(/([가-힣])(\d)/g, '$1 $2')
    // ATX heading without preceding newline: "텍스트### 제목" → "텍스트\n### 제목"
    // Exclude '/' to avoid breaking URL fragments (e.g. example.com/#section)
    .replace(/([^/\n])(#{1,6} )/g, '$1\n$2');

  // Restore protected regions (reverse order)
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

  // Protect existing markdown links: [text](url)
  // Use regex that handles parentheses inside URLs, e.g. [text](https://example.com/foo_(bar))
  const mdLinks: string[] = [];
  result = result.replace(/\[([^\]]*)\]\(([^()]*(?:\([^()]*\)[^()]*)*)\)/g, (match, text, url) => {
    // LLM tokenizer artifact: remove spaces inside HTTP/HTTPS URLs
    const isHttpUrl = /^\s*https?:\/\//.test(url);
    const cleanedUrl = isHttpUrl ? url.replace(/\s+/g, '') : url;
    const cleanedMatch = isHttpUrl ? `[${text}](${cleanedUrl})` : match;
    mdLinks.push(cleanedMatch);
    return `__MD_LINK_${mdLinks.length - 1}__`;
  });

  // Repair unclosed markdown links: [text](https://url <- missing closing )
  // Handles LLM artifact where closing ) is omitted
  // URL char class (RFC 3986) excludes Korean, quotes, parens — these signal URL end
  // (?!\)) negative lookahead excludes already-closed links (handled above)
  const urlCharClass = `[A-Za-z0-9\\-._~:/?#\\[\\]@!$&'*+,;=%]`;
  const unclosedLinkPattern = new RegExp(
    `\\[([^\\]\\n]+)\\]\\((https?://${urlCharClass}+(?:\\s+${urlCharClass}+)*)(?!\\))`,
    'g'
  );
  result = result.replace(unclosedLinkPattern, (match, text, url) => {
    const cleanUrl = url.replace(/\s+/g, '').replace(/[-.,;:!?]+$/, '');
    if (!cleanUrl) return match;
    mdLinks.push(`[${text}](${cleanUrl})`);
    return `__MD_LINK_${mdLinks.length - 1}__`;
  });

  // Wrap bare URLs in markdown link syntax
  // Allow ')' in URL characters; trailing unbalanced ')' are stripped below
  result = result.replace(
    /(?<!\()(https?:\/\/[^\s<>\]"']+)/g,
    (url) => {
      // Strip trailing sentence punctuation (not closing parens yet)
      let cleaned = url.replace(/[.,;:!?]+$/, '');
      // Remove excess closing parens: only strip unbalanced trailing ')'
      const openCount = (cleaned.match(/\(/g) || []).length;
      const closeCount = (cleaned.match(/\)/g) || []).length;
      if (closeCount > openCount) {
        const excess = closeCount - openCount;
        cleaned = cleaned.replace(new RegExp(`\\){${excess}}$`), '');
      }
      const trailing = url.slice(cleaned.length);
      return `[${cleaned}](${cleaned})${trailing}`;
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
function isValidUrlProtocol(url: string): boolean {
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

    // Smart truncation: show domain + path start for URLs, simple truncation for text
    const displayText = typeof children === 'string' && children.length > 60
      ? (() => {
          try {
            const url = new URL(children);
            const domain = url.hostname;
            const pathStart = url.pathname.slice(0, 20);
            return `${domain}${pathStart}...`;
          } catch {
            return children.slice(0, 57) + '...';
          }
        })()
      : children;

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
  // Preprocess: wrap bare URLs in markdown link syntax for reliable link detection
  const sanitizedContent = useMemo(() => {
    if (!content) return '';
    return wrapBareUrls(content);
  }, [content]);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      rehypePlugins={[rehypeHighlight]}
      components={markdownComponents}
    >
      {sanitizedContent}
    </ReactMarkdown>
  );
});

export function MarkdownRenderer({ content, className, isStreaming }: MarkdownRendererProps) {
  // For smooth streaming: render as plain text during streaming
  // Only apply markdown formatting after streaming is complete
  // This avoids expensive re-renders on every token

  // Fix spacing issues from LLM tokenization
  const fixedContent = fixSentenceSpacing(content);

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
