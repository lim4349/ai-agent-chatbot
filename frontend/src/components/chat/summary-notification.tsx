'use client';

import { useEffect } from 'react';
import { X, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface SummaryNotificationProps {
  isVisible: boolean;
  onDismiss: () => void;
  summaryPreview?: string;
}

const SUMMARY_PREVIEW_LENGTH = 100;

export function SummaryNotification({
  isVisible,
  onDismiss,
  summaryPreview,
}: SummaryNotificationProps) {
  // Auto-dismiss after 8 seconds
  useEffect(() => {
    if (!isVisible) return;

    const timer = setTimeout(() => {
      onDismiss();
    }, 8000);

    return () => clearTimeout(timer);
  }, [isVisible, onDismiss]);

  if (!isVisible) return null;

  const truncatedPreview = summaryPreview
    ? summaryPreview.slice(0, SUMMARY_PREVIEW_LENGTH) +
      (summaryPreview.length > SUMMARY_PREVIEW_LENGTH ? '...' : '')
    : null;

  return (
    <div
      className={cn(
        'fixed bottom-4 right-4 z-50 max-w-md',
        'bg-card border border-border rounded-lg shadow-lg',
        'p-4 animate-in slide-in-from-bottom-4 fade-in duration-300'
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <FileText className="w-4 h-4 text-primary" />
        </div>

        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold mb-1">
            대화가 요약되었습니다
          </h4>
          {truncatedPreview && (
            <p className="text-xs text-muted-foreground line-clamp-2">
              {truncatedPreview}
            </p>
          )}
        </div>

        <Button
          variant="ghost"
          size="icon-xs"
          className="flex-shrink-0 -mr-1 -mt-1 text-muted-foreground hover:text-foreground"
          onClick={onDismiss}
        >
          <X className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}
