'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Trash2, MessageSquare, Loader2 } from 'lucide-react';
import type { Session } from '@/types';
import { useTranslation } from '@/lib/i18n';
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
  onDelete: () => void | Promise<void>;
}

export function SessionItem({
  session,
  isActive,
  onSelect,
  onDelete,
}: SessionItemProps) {
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const { locale } = useTranslation();

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect();
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete();
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
    }
  };

  // Get last message for preview (limited to 50 chars)
  const messageCount = session.messages?.length || 0;
  const lastMessage = messageCount > 0
    ? session.messages[messageCount - 1].content.slice(0, 50)
    : null;

  // Translations
  const isKorean = locale === 'ko';
  const title = isKorean ? '세션 삭제' : 'Delete session?';
  const description = isKorean
    ? `"${session.title}"을(를) 삭제하시겠습니까?`
    : `Are you sure you want to delete "${session.title}"?`;
  const lastPrefix = isKorean ? '마지막: ' : 'Last: ';
  const warning = isKorean
    ? '이 작업은 되돌릴 수 없습니다.'
    : 'This action cannot be undone.';
  const cancelLabel = isKorean ? '취소' : 'Cancel';
  const deleteLabel = isKorean ? '삭제' : 'Delete';
  const deletingLabel = isKorean ? '삭제 중...' : 'Deleting...';

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
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        aria-label={session.title}
        title={session.title}
      >
        <MessageSquare className="w-4 h-4 flex-shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="flex-1 min-w-0 truncate text-sm" title={session.title}>
          {session.title}
        </span>
        <button
          type="button"
          className={cn(
            'flex-shrink-0 p-2 rounded-md text-muted-foreground hover:text-red-500 hover:bg-red-500/10 transition-all',
            'opacity-0 group-hover:opacity-100 focus:opacity-100',
            'md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100'
          )}
          onClick={(e) => {
            e.stopPropagation();
            setIsDeleteDialogOpen(true);
          }}
          aria-label={isKorean ? `"${session.title}" 세션 삭제` : `Delete session "${session.title}"`}
          disabled={isDeleting}
        >
          {isDeleting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Trash2 className="w-4 h-4" />
          )}
        </button>
      </div>

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{title}</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>{description}</p>
              {lastMessage && (
                <p className="text-muted-foreground text-sm break-words border-l-2 border-border pl-2 max-w-full">
                  {lastPrefix}{lastMessage}...
                </p>
              )}
              <p className="text-destructive font-medium">{warning}</p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>{cancelLabel}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-500 hover:bg-red-600"
              disabled={isDeleting}
            >
              {isDeleting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {deletingLabel}
                </>
              ) : (
                deleteLabel
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
