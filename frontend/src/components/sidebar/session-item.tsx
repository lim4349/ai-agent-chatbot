'use client';

import { cn } from '@/lib/utils';
import { Trash2, MessageSquare } from 'lucide-react';
import type { Session } from '@/types';

interface SessionItemProps {
  session: Session;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

export function SessionItem({
  session,
  isActive,
  onSelect,
  onDelete,
}: SessionItemProps) {
  return (
    <div
      className={cn(
        'group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors',
        isActive
          ? 'bg-primary/10 text-primary'
          : 'hover:bg-muted text-foreground'
      )}
      onClick={onSelect}
    >
      <MessageSquare className="w-4 h-4 flex-shrink-0 text-muted-foreground" />
      <span className="flex-1 min-w-0 truncate text-sm">{session.title}</span>
      <button
        type="button"
        className="flex-shrink-0 p-2 rounded-md text-muted-foreground opacity-40 hover:text-red-500 hover:opacity-100 hover:bg-red-500/10 transition-colors"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        aria-label="Delete session"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );
}
