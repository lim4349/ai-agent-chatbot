'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Trash2, MessageSquare } from 'lucide-react';
import type { Session } from '@/types';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

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
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  const handleDelete = () => {
    onDelete();
    setIsDeleteDialogOpen(false);
  };

  return (
    <>
      <div
        className={cn(
          'group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors',
          isActive
            ? 'bg-primary/10 text-primary'
            : 'hover:bg-muted text-foreground'
        )}
        onClick={onSelect}
        role="button"
        tabIndex={0}
        aria-label={session.title}
      >
        <MessageSquare className="w-4 h-4 flex-shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="flex-1 min-w-0 truncate text-sm">{session.title}</span>
        <button
          type="button"
          className="flex-shrink-0 p-2 rounded-md text-muted-foreground opacity-40 hover:text-red-500 hover:opacity-100 hover:bg-red-500/10 transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            setIsDeleteDialogOpen(true);
          }}
          aria-label="Delete session"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete session?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{session.title}&quot;? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-500 hover:bg-red-600">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
