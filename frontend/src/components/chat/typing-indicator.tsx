'use client';

import { cn } from '@/lib/utils';

interface TypingIndicatorProps {
  className?: string;
}

export function TypingIndicator({ className }: TypingIndicatorProps) {
  return (
    <div className={cn('flex items-center gap-1', className)}>
      <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-duration:0.6s] [animation-delay:-0.2s]" />
      <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-duration:0.6s] [animation-delay:-0.1s]" />
      <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-duration:0.6s]" />
    </div>
  );
}
