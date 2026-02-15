'use client';

import { cn } from '@/lib/utils';
import { FileText, Plus } from 'lucide-react';

interface ContextSeparatorProps {
  label: string;
  type?: 'summary' | 'new-topic';
}

export function ContextSeparator({ label, type = 'new-topic' }: ContextSeparatorProps) {
  const isSummary = type === 'summary';

  return (
    <div className="flex items-center gap-3 my-6 px-4">
      <div className="flex-1 h-px bg-border" />
      <div
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium',
          isSummary
            ? 'bg-primary/10 text-primary border border-primary/20'
            : 'bg-muted text-muted-foreground border border-border'
        )}
      >
        {isSummary ? (
          <FileText className="w-3.5 h-3.5" />
        ) : (
          <Plus className="w-3.5 h-3.5" />
        )}
        <span>{label}</span>
      </div>
      <div className="flex-1 h-px bg-border" />
    </div>
  );
}
