'use client';

import { useState, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import { Bot, User, Copy, Check } from 'lucide-react';
import type { Message } from '@/types';
import { AgentBadge } from './agent-badge';
import { ToolUsage } from './tool-usage';
import { MemoryReference } from './memory-reference';
import { AgentSwitchAnimation } from './agent-switch-animation';
import { MarkdownRenderer } from './markdown-renderer';
import { useTranslation } from '@/lib/i18n';

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
  previousAgent?: string;
  onHeightChange?: (height: number) => void;
}

export function MessageBubble({ message, isStreaming, previousAgent, onHeightChange }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);
  const { t } = useTranslation();
  const elementRef = useRef<HTMLDivElement>(null);

  // Measure height and report to parent for react-window
  useEffect(() => {
    if (elementRef.current && onHeightChange) {
      const height = elementRef.current.offsetHeight;
      if (height > 0) {
        onHeightChange(height);
      }
    }
  }, [elementRef, message.content, onHeightChange]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      ref={elementRef}
      className={cn(
        'group relative flex gap-3 px-4 py-3 transition-colors hover:bg-muted/20 overflow-hidden',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-0.5',
          isUser ? 'bg-primary' : 'bg-muted border border-border'
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-primary-foreground" />
        ) : (
          <Bot className="w-4 h-4 text-foreground" />
        )}
      </div>

      {/* Content */}
      <div
        className={cn(
          'flex flex-col gap-1.5 max-w-[80%] min-w-0',
          isUser ? 'items-end' : 'items-start'
        )}
      >
        {/* Agent badge and switch animation */}
        {!isUser && (
          <div className="flex items-center gap-2 flex-wrap">
            {message.agent && <AgentBadge agent={message.agent} />}
            <AgentSwitchAnimation
              fromAgent={previousAgent}
              toAgent={message.agent || 'chat'}
              isVisible={!!previousAgent && previousAgent !== message.agent}
            />
          </div>
        )}

        {/* Memory reference indicator */}
        {!isUser && message.hasMemoryReference && (
          <MemoryReference
            hasMemoryReference={message.hasMemoryReference}
            referencedTopics={message.referencedTopics}
          />
        )}

        {/* Message bubble */}
        <div
          className={cn(
            'relative rounded-2xl px-4 py-3 cursor-text select-text',
            isUser
              ? 'bg-primary text-primary-foreground rounded-br-md'
              : 'bg-muted/50 border border-border/50 rounded-bl-md'
          )}
        >
          {isUser ? (
            <p className="text-[15px] leading-[1.75] whitespace-pre-wrap break-words">
              {message.content}
            </p>
          ) : (
            <div aria-live={isStreaming ? 'polite' : undefined} aria-atomic="true">
              <MarkdownRenderer content={message.content} isStreaming={isStreaming} />
            </div>
          )}

          {/* Streaming cursor - only show when there's actual content */}
          {isStreaming && !isUser && message.content && (
            <span className="inline-block w-0.5 h-5 bg-foreground/70 ml-0.5 animate-pulse [animation-duration:0.8s] align-text-bottom" aria-hidden="true" />
          )}
        </div>

        {/* Tool usage display */}
        {!isUser && message.tools && message.tools.length > 0 && (
          <ToolUsage tools={message.tools} />
        )}

        {/* Bottom row: timestamp + copy button */}
        <div
          className={cn(
            'flex items-center gap-2 px-1',
            isUser ? 'flex-row-reverse' : 'flex-row'
          )}
        >
          <span className="text-xs text-muted-foreground" suppressHydrationWarning>
            {typeof message.createdAt === 'string'
              ? new Date(message.createdAt).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })
              : ''}
          </span>

          {/* Copy button - visible on hover for desktop, always visible on mobile */}
          {message.content && !isStreaming && (
            <button
              onClick={handleCopy}
              className={cn(
                'flex items-center justify-center gap-1 text-xs transition-all rounded-md min-w-[44px] min-h-[44px]',
                copied
                  ? 'text-green-400 opacity-100'
                  : 'text-muted-foreground/50 opacity-0 md:opacity-0 group-hover:opacity-100 md:group-hover:opacity-100 hover:text-foreground hover:bg-muted/50',
                // Always visible on mobile (touch devices)
                'hover:opacity-100 active:opacity-100'
              )}
              title={t('chat.copyMessage')}
              aria-label={t('chat.copyMessage')}
            >
              {copied ? (
                <Check className="w-4 h-4" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
