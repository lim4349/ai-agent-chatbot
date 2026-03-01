'use client';

import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
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

// Time to pause auto-scroll after user manually scrolls (ms)
const SCROLL_PAUSE_DURATION = 2000;

export function MessageList({ messages, isStreaming }: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation();
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const prevMessagesLengthRef = useRef(messages.length);

  // Track user scroll interaction for pausing auto-scroll
  const scrollPauseTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [isScrollPaused, setIsScrollPaused] = useState(false);
  const isUserScrollingRef = useRef(false);

  // Check if user is near bottom
  const checkScrollPosition = useCallback(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const threshold = 100;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const nearBottom = distanceFromBottom < threshold;
    setIsNearBottom(nearBottom);
    setShowScrollButton(!nearBottom);
  }, []);

  // Handle user scroll with pause mechanism
  const handleScroll = useCallback(() => {
    // Mark that user is actively scrolling
    isUserScrollingRef.current = true;

    // Pause auto-scroll for SCROLL_PAUSE_DURATION
    if (!isScrollPaused) {
      setIsScrollPaused(true);
    }

    // Clear existing timeout
    if (scrollPauseTimeoutRef.current) {
      clearTimeout(scrollPauseTimeoutRef.current);
    }

    // Set new timeout to resume auto-scroll
    scrollPauseTimeoutRef.current = setTimeout(() => {
      setIsScrollPaused(false);
      isUserScrollingRef.current = false;
    }, SCROLL_PAUSE_DURATION);

    // Update scroll position state
    checkScrollPosition();
  }, [checkScrollPosition, isScrollPaused]);

  // Auto-scroll on new messages
  useEffect(() => {
    const hasNewMessage = messages.length > prevMessagesLengthRef.current;
    prevMessagesLengthRef.current = messages.length;

    if ((hasNewMessage || isNearBottom) && scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages.length, isNearBottom]);

  // Scroll during streaming - respects user scroll pause
  useEffect(() => {
    if (!isStreaming || !isNearBottom || isScrollPaused) return;

    const interval = setInterval(() => {
      if (scrollRef.current && isNearBottom && !isScrollPaused) {
        scrollRef.current.scrollIntoView({ behavior: 'auto' });
      }
    }, 100);

    return () => clearInterval(interval);
  }, [isStreaming, isNearBottom, isScrollPaused]);

  // Cleanup scroll pause timeout on unmount
  useEffect(() => {
    return () => {
      if (scrollPauseTimeoutRef.current) {
        clearTimeout(scrollPauseTimeoutRef.current);
      }
    };
  }, []);

  // Scroll to bottom function
  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
      setIsNearBottom(true);
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="relative flex-1 min-h-0">
      <div
        ref={containerRef}
        className="h-full overflow-y-auto overflow-x-hidden"
        onScroll={handleScroll}
      >
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
          <div className="py-4 space-y-0">
            <div className="max-w-3xl mx-auto w-full">
              {useMemo(() => {
                return messages.map((message, index) => {
                  // Don't render empty streaming assistant message
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
                });
              }, [messages, isStreaming])}
              {/* Typing indicator shown when streaming starts but no content yet */}
              {isStreaming && messages[messages.length - 1]?.content === '' && (
                <div className="flex gap-3 px-4 py-5">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-muted border border-border">
                    <Bot className="w-4 h-4 text-foreground" />
                  </div>
                  <div className="flex items-center">
                    <TypingIndicator />
                  </div>
                </div>
              )}
              <div ref={scrollRef} className="h-1" />
            </div>
          </div>
        )}
      </div>

      {/* Scroll to bottom button */}
      <button
        onClick={scrollToBottom}
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
