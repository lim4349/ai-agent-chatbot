'use client';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
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
      <Button
        variant="ghost"
        size="icon"
        className="flex-shrink-0 opacity-0 group-hover:opacity-100 h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-opacity"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        aria-label="Delete session"
      >
        <Trash2 className="w-4 h-4" />
      </Button>
    </div>
  );
}
