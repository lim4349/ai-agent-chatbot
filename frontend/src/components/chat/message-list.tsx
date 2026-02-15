'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Bot, MessageSquare, ArrowDown } from 'lucide-react';
import type { Message } from '@/types';
import { MessageBubble } from './message-bubble';
import { TypingIndicator } from './typing-indicator';
import { useTranslation } from '@/lib/i18n';
import { cn } from '@/lib/utils';

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
}

export function MessageList({ messages, isStreaming }: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLElement | null>(null);
  const { t } = useTranslation();
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const lastMessageCount = useRef(messages.length);
  const isUserScrolling = useRef(false);
  const scrollTimeout = useRef<NodeJS.Timeout | null>(null);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    if (viewportRef.current && isNearBottom) {
      viewportRef.current.scrollTo({
        top: viewportRef.current.scrollHeight,
        behavior,
      });
    }
  }, [isNearBottom]);

  // Track scroll position with debounce
  const handleScroll = useCallback(() => {
    if (!viewportRef.current) return;

    const viewport = viewportRef.current;
    const threshold = 100;
    const distanceFromBottom =
      viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
    const nearBottom = distanceFromBottom < threshold;

    setIsNearBottom(nearBottom);
    setShowScrollButton(!nearBottom && isStreaming);

    // Detect user-initiated scroll
    isUserScrolling.current = true;
    if (scrollTimeout.current) {
      clearTimeout(scrollTimeout.current);
    }
    scrollTimeout.current = setTimeout(() => {
      isUserScrolling.current = false;
    }, 150);
  }, [isStreaming]);

  // Get viewport reference
  useEffect(() => {
    const viewport = scrollRef.current?.closest('[data-radix-scroll-area-viewport]');
    if (viewport) {
      viewportRef.current = viewport as HTMLElement;
      viewport.addEventListener('scroll', handleScroll);
      handleScroll(); // Initial check
      return () => {
        viewport.removeEventListener('scroll', handleScroll);
        if (scrollTimeout.current) clearTimeout(scrollTimeout.current);
      };
    }
  }, [handleScroll]);

  // Auto-scroll on new messages (not during streaming content updates)
  useEffect(() => {
    const hasNewMessage = messages.length > lastMessageCount.current;
    lastMessageCount.current = messages.length;

    if (hasNewMessage && isNearBottom) {
      scrollToBottom('smooth');
    }
  }, [messages.length, isNearBottom, scrollToBottom]);

  // Streaming scroll - only if user is near bottom and not actively scrolling
  useEffect(() => {
    if (!isStreaming || !isNearBottom) return;

    let rafId: number;
    let lastScrollTime = Date.now();

    const checkAndScroll = () => {
      const now = Date.now();
      // Only scroll every 100ms max, and only if user isn't actively scrolling
      if (now - lastScrollTime > 100 && !isUserScrolling.current && isNearBottom) {
        scrollToBottom('auto');
        lastScrollTime = now;
      }
      rafId = requestAnimationFrame(checkAndScroll);
    };

    rafId = requestAnimationFrame(checkAndScroll);
    return () => cancelAnimationFrame(rafId);
  }, [isStreaming, isNearBottom, scrollToBottom]);

  const isEmpty = messages.length === 0;

  return (
    <div className="relative flex-1 min-h-0">
      <ScrollArea className="h-full" suppressHydrationWarning>
        <div className="min-h-full">
          {isEmpty ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-8 min-h-[400px] gap-3">
              <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center">
                <MessageSquare className="w-8 h-8" />
              </div>
              <p className="text-lg font-medium">{t('chat.placeholder')}</p>
              <p className="text-sm text-center max-w-sm">
                {t('chat.placeholderSub')}
              </p>
            </div>
          ) : (
            <div className="flex flex-col py-4">
              {messages.map((message, index) => {
                // Don't render empty streaming assistant message - show TypingIndicator instead
                const isEmptyStreaming =
                  isStreaming &&
                  index === messages.length - 1 &&
                  message.role === 'assistant' &&
                  message.content === '';

                if (isEmptyStreaming) return null;

                return (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    isStreaming={
                      isStreaming && index === messages.length - 1 && message.role === 'assistant'
                    }
                  />
                );
              })}
              {/* Typing indicator shown when streaming starts but no content yet */}
              {isStreaming && messages[messages.length - 1]?.content === '' && (
                <div className="flex gap-3 p-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-muted border border-border">
                    <Bot className="w-4 h-4 text-foreground" />
                  </div>
                  <div className="bg-muted rounded-2xl rounded-bl-md px-4 py-3">
                    <TypingIndicator />
                  </div>
                </div>
              )}
              <div ref={scrollRef} className="h-1" />
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Scroll to bottom button */}
      <button
        onClick={() => {
          setIsNearBottom(true);
          scrollToBottom('smooth');
        }}
        className={cn(
          'absolute bottom-4 right-4 z-10',
          'w-10 h-10 rounded-full bg-primary text-primary-foreground',
          'flex items-center justify-center shadow-lg',
          'transition-all duration-200 hover:scale-110',
          'focus:outline-none focus:ring-2 focus:ring-primary/50',
          showScrollButton
            ? 'opacity-100 translate-y-0'
            : 'opacity-0 translate-y-4 pointer-events-none'
        )}
        aria-label="Scroll to bottom"
      >
        <ArrowDown className="w-5 h-5" />
      </button>
    </div>
  );
}
