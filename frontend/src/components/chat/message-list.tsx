'use client';

import { useEffect, useRef, useState } from 'react';
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
  const containerRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation();
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const prevMessagesLengthRef = useRef(messages.length);

  // Check if user is near bottom
  const checkScrollPosition = () => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const threshold = 100;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const nearBottom = distanceFromBottom < threshold;
    setIsNearBottom(nearBottom);
    setShowScrollButton(!nearBottom);
  };

  // Auto-scroll on new messages
  useEffect(() => {
    const hasNewMessage = messages.length > prevMessagesLengthRef.current;
    prevMessagesLengthRef.current = messages.length;

    if ((hasNewMessage || isNearBottom) && scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages.length, isNearBottom]);

  // Scroll during streaming
  useEffect(() => {
    if (!isStreaming || !isNearBottom) return;

    const interval = setInterval(() => {
      if (scrollRef.current && isNearBottom) {
        scrollRef.current.scrollIntoView({ behavior: 'auto' });
      }
    }, 100);

    return () => clearInterval(interval);
  }, [isStreaming, isNearBottom]);

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
        onScroll={checkScrollPosition}
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
          <div className="py-4 space-y-4">
            {messages.map((message, index) => {
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
