'use client';

import { FileText, FileCode, FileSpreadsheet, File as FileIcon, Trash2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { DocumentInfo } from '@/types';

interface DocumentListProps {
  documents: DocumentInfo[];
  onDelete: (id: string) => void;
  isLoading: boolean;
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

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
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

export function DocumentList({ documents, onDelete, isLoading }: DocumentListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="p-4 rounded-full bg-muted mb-4">
          <FileIcon className="w-8 h-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-medium mb-1">No documents yet</h3>
        <p className="text-sm text-muted-foreground max-w-xs">
          Upload documents to add them to the knowledge base. They will be used to answer your questions.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {documents.map((doc) => {
        const Icon = getFileIcon(doc.file_type);
        const fileTypeLabel = getFileTypeLabel(doc.file_type);

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
                <span>{formatDate(doc.upload_time)}</span>
              </div>
            </div>

            <div className="hidden sm:flex items-center gap-4 text-sm text-muted-foreground">
              <div className="text-right">
                <p className="font-medium tabular-nums">{formatNumber(doc.chunk_count)}</p>
                <p className="text-xs">chunks</p>
              </div>
              <div className="text-right">
                <p className="font-medium tabular-nums">{formatNumber(doc.total_tokens)}</p>
                <p className="text-xs">tokens</p>
              </div>
            </div>

            <Button
              variant="ghost"
              size="icon"
              className="text-muted-foreground hover:text-destructive"
              onClick={() => {
                if (confirm(`Are you sure you want to delete "${doc.filename}"?`)) {
                  onDelete(doc.id);
                }
              }}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        );
      })}
    </div>
  );
}
