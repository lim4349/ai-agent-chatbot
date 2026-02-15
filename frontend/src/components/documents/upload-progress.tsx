'use client';

import { Loader2, CheckCircle, XCircle, FileText, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatFileSize, MAX_FILE_SIZE } from '@/lib/file-validation';

interface UploadProgressProps {
  filename: string;
  progress: number; // 0-100
  status: 'uploading' | 'processing' | 'completed' | 'error';
  error?: string;
  fileSize?: number;
  validationErrors?: string[];
  validationWarnings?: string[];
}

const statusConfig = {
  uploading: {
    icon: Loader2,
    iconClass: 'animate-spin text-primary',
    label: 'Uploading...',
    barColor: 'bg-primary',
  },
  processing: {
    icon: Loader2,
    iconClass: 'animate-spin text-blue-500',
    label: 'Processing...',
    barColor: 'bg-blue-500',
  },
  completed: {
    icon: CheckCircle,
    iconClass: 'text-green-500',
    label: 'Completed',
    barColor: 'bg-green-500',
  },
  error: {
    icon: XCircle,
    iconClass: 'text-destructive',
    label: 'Error',
    barColor: 'bg-destructive',
  },
};

export function UploadProgress({
  filename,
  progress,
  status,
  error,
  fileSize,
  validationErrors = [],
  validationWarnings = [],
}: UploadProgressProps) {
  const config = statusConfig[status];
  const Icon = config.icon;

  // Truncate filename if too long
  const displayFilename =
    filename.length > 40 ? `${filename.slice(0, 37)}...` : filename;

  // Calculate file size percentage if size is provided
  const sizePercentage = fileSize ? Math.min((fileSize / MAX_FILE_SIZE) * 100, 100) : 0;
  const sizeStatus = fileSize ? (sizePercentage >= 100 ? 'error' : sizePercentage >= 80 ? 'warning' : 'ok') : 'ok';

  return (
    <div className="w-full space-y-3 p-4 border rounded-lg bg-card">
      {/* File Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-md bg-primary/10 flex-shrink-0">
          <FileText className="w-5 h-5 text-primary" />
        </div>

        <div className="flex-1 min-w-0">
          {/* Filename with status badge */}
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium truncate" title={filename}>
              {displayFilename}
            </p>
            {!validationErrors.length && status === 'error' && (
              <span className="flex-shrink-0 px-2 py-0.5 text-xs font-medium rounded-full bg-destructive/10 text-destructive">
                Failed
              </span>
            )}
            {status === 'completed' && (
              <span className="flex-shrink-0 px-2 py-0.5 text-xs font-medium rounded-full bg-green-500/10 text-green-600 dark:text-green-500">
                Success
              </span>
            )}
          </div>

          {/* Status row */}
          <div className="flex items-center gap-2 mt-1">
            <Icon className={cn('w-4 h-4 flex-shrink-0', config.iconClass)} />
            <span
              className={cn(
                'text-xs',
                status === 'error' ? 'text-destructive' : 'text-muted-foreground'
              )}
            >
              {config.label}
            </span>

            {/* File size display */}
            {fileSize && status !== 'error' && (
              <>
                <span className="text-xs text-muted-foreground">•</span>
                <span className="text-xs text-muted-foreground">
                  {formatFileSize(fileSize)} / {formatFileSize(MAX_FILE_SIZE)}
                </span>
              </>
            )}

            {/* Size status indicator */}
            {fileSize && sizeStatus === 'error' && status !== 'completed' && (
              <span className="px-1.5 py-0.5 text-xs font-medium rounded bg-destructive/10 text-destructive">
                Too large
              </span>
            )}
          </div>
        </div>

        {/* Progress percentage */}
        <span className="text-sm font-medium tabular-nums flex-shrink-0">
          {Math.round(progress)}%
        </span>
      </div>

      {/* Main progress bar */}
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-secondary">
        <div
          className={cn(
            'h-full transition-all duration-300 ease-out',
            config.barColor,
            status === 'error' && 'animate-pulse'
          )}
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* File size indicator bar (shows size relative to limit) */}
      {fileSize && status !== 'completed' && status !== 'error' && (
        <div className="space-y-1">
          <div className="relative h-1 w-full overflow-hidden rounded-full bg-secondary/50">
            <div
              className={cn(
                'h-full transition-all duration-300 ease-out',
                sizeStatus === 'error' && 'bg-destructive/60',
                sizeStatus === 'warning' && 'bg-yellow-500/60',
                sizeStatus === 'ok' && 'bg-muted-foreground/30'
              )}
              style={{ width: `${sizePercentage}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground text-right">
            {sizePercentage.toFixed(0)}% of size limit
          </p>
        </div>
      )}

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <div className="space-y-2 p-3 rounded-md bg-destructive/10 border border-destructive/20">
          <div className="flex items-start gap-2">
            <XCircle className="w-4 h-4 text-destructive flex-shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1">
              <p className="text-sm font-medium text-destructive">
                {validationErrors.length === 1 ? 'Error' : `${validationErrors.length} Errors`}
              </p>
              <ul className="space-y-1">
                {validationErrors.map((err, index) => (
                  <li key={index} className="text-xs text-destructive">
                    • {err}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Validation Warnings */}
      {validationWarnings.length > 0 && (
        <div className="space-y-2 p-3 rounded-md bg-yellow-500/10 border border-yellow-500/20">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-600 dark:text-yellow-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1">
              <p className="text-sm font-medium text-yellow-600 dark:text-yellow-500">
                {validationWarnings.length === 1 ? 'Warning' : `${validationWarnings.length} Warnings`}
              </p>
              <ul className="space-y-1">
                {validationWarnings.map((warn, index) => (
                  <li key={index} className="text-xs text-yellow-600 dark:text-yellow-500">
                    • {warn}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Upload Error */}
      {error && validationErrors.length === 0 && (
        <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20">
          <p className="text-xs text-destructive">{error}</p>
        </div>
      )}
    </div>
  );
}
