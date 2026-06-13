'use client';

import { AlertTriangle, FileText, FileCode, FileSpreadsheet, File as FileIcon, Trash2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTranslation } from '@/lib/i18n';
import { cn } from '@/lib/utils';
import type { DocumentInfo } from '@/types';

interface DocumentListProps {
  documents: DocumentInfo[];
  onDelete: (id: string) => Promise<void> | void;
  isLoading: boolean;
  deletingDocumentIds?: string[];
  error?: string | null;
}

const FILE_TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  'application/pdf': FileText,
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': FileText,
  'text/plain': FileText,
  'text/markdown': FileCode,
  'text/csv': FileSpreadsheet,
  'application/json': FileCode,
};

const FILE_TYPE_LABELS: Record<string, string> = {
  'application/pdf': 'PDF',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word',
  'text/plain': 'Text',
  'text/markdown': 'Markdown',
  'text/csv': 'CSV',
  'application/json': 'JSON',
};

function getFileIcon(fileType: string) {
  return FILE_TYPE_ICONS[fileType] || FileIcon;
}

function getFileTypeLabel(fileType: string) {
  return FILE_TYPE_LABELS[fileType] || fileType.split('/').pop()?.toUpperCase() || 'File';
}

function formatDate(dateString: string, locale: 'ko' | 'en'): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat(locale === 'ko' ? 'ko-KR' : 'en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`;
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`;
  }
  return num.toString();
}

export function DocumentList({
  documents,
  onDelete,
  isLoading,
  deletingDocumentIds = [],
  error,
}: DocumentListProps) {
  const { locale, t } = useTranslation();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span>{t('doc.loading')}</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
        {t('doc.fetchError')}: {error}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="p-4 rounded-full bg-muted mb-4">
          <FileIcon className="w-8 h-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-medium mb-1">{t('doc.noDocumentsTitle')}</h3>
        <p className="text-sm text-muted-foreground max-w-xs">
          {t('doc.noDocumentsDescription')}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {documents.map((doc) => {
        const Icon = getFileIcon(doc.file_type);
        const fileTypeLabel = getFileTypeLabel(doc.file_type);
        const isDeleting = deletingDocumentIds.includes(doc.id);
        const warningCount = doc.warnings?.length ?? 0;
        const searchChunkCount = doc.child_chunk_count || doc.chunk_count;

        return (
          <div
            key={doc.id}
            className={cn(
              'flex items-center gap-4 p-4 border rounded-lg bg-card',
              'hover:bg-accent/50 transition-colors'
            )}
          >
            <div className="p-3 rounded-md bg-primary/10">
              <Icon className="w-6 h-6 text-primary" />
            </div>

            <div className="flex-1 min-w-0">
              <p className="font-medium truncate" title={doc.filename}>
                {doc.filename}
              </p>
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <span className="px-2 py-0.5 rounded-full bg-secondary text-xs">
                  {fileTypeLabel}
                </span>
                <span>{formatDate(doc.upload_time, locale)}</span>
                {!!doc.page_count && <span>{t('doc.pages', doc.page_count)}</span>}
                {!!doc.table_count && <span>{t('doc.tables', doc.table_count)}</span>}
              </div>
              {warningCount > 0 && (
                <div className="mt-1 flex items-center gap-1 text-xs text-amber-600">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  <span>{t('doc.parseWarnings', warningCount)}</span>
                </div>
              )}
            </div>

            <div className="hidden sm:flex items-center gap-4 text-sm text-muted-foreground">
              <div className="text-right">
                <p className="font-medium tabular-nums">{formatNumber(searchChunkCount)}</p>
                <p className="text-xs">
                  {doc.child_chunk_count ? t('doc.searchChunks') : t('doc.chunks')}
                </p>
              </div>
              <div className="text-right">
                <p className="font-medium tabular-nums">{formatNumber(doc.total_tokens)}</p>
                <p className="text-xs">{t('doc.tokens')}</p>
              </div>
            </div>

            <Button
              variant="ghost"
              size="icon"
              className="text-muted-foreground hover:text-destructive"
              disabled={isDeleting}
              aria-label={isDeleting ? t('doc.deleting') : t('doc.removeFile')}
              onClick={() => {
                if (confirm(t('doc.deleteConfirm', doc.filename))) {
                  void onDelete(doc.id);
                }
              }}
            >
              {isDeleting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
            </Button>
          </div>
        );
      })}
    </div>
  );
}
