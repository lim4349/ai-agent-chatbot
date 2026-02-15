'use client';

import { useCallback, useState } from 'react';
import { useDropzone, type Accept } from 'react-dropzone';
import { Upload, FileText, AlertCircle, FileWarning, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/lib/i18n';
import {
  validateFile,
  formatFileSize,
  getFileSizePercentage,
  getFileSizeStatus,
  FILE_TYPE_LABELS,
  ALLOWED_FILE_TYPES,
  MAX_FILE_SIZE,
  type ValidationError,
  type ValidationResult,
} from '@/lib/file-validation';

interface FileUploadZoneProps {
  onUpload: (file: File) => void;
  isUploading: boolean;
  acceptedTypes?: string[];
}

interface FilePreview {
  file: File;
  validation: ValidationResult;
  sizePercentage: number;
  sizeStatus: 'ok' | 'warning' | 'error';
  fileTypeLabel: string;
}

export function FileUploadZone({
  onUpload,
  isUploading,
  acceptedTypes = ALLOWED_FILE_TYPES as unknown as string[],
}: FileUploadZoneProps) {
  const [filePreview, setFilePreview] = useState<FilePreview | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const { t } = useTranslation();

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      const file = acceptedFiles[0];
      setIsValidating(true);

      try {
        // Validate the file
        const validation = await validateFile(file);

        const preview: FilePreview = {
          file,
          validation,
          sizePercentage: getFileSizePercentage(file.size),
          sizeStatus: getFileSizeStatus(file.size),
          fileTypeLabel: FILE_TYPE_LABELS[file.type] || 'Unknown',
        };

        setFilePreview(preview);

        // If valid, trigger upload after a short delay
        if (validation.isValid) {
          setTimeout(() => {
            onUpload(file);
            setFilePreview(null);
          }, 500);
        }
      } catch (error) {
        console.error('Validation error:', error);
      } finally {
        setIsValidating(false);
      }
    },
    [onUpload]
  );

  const handleClearPreview = useCallback(() => {
    setFilePreview(null);
  }, []);

  const acceptConfig: Accept = {};
  acceptedTypes.forEach((type) => {
    acceptConfig[type] = [];
  });

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: acceptConfig,
    multiple: false,
    disabled: isUploading || isValidating,
  });

  const acceptedTypeLabels = acceptedTypes
    .map((type) => FILE_TYPE_LABELS[type] || type)
    .filter(Boolean)
    .join(', ');

  // If we have a file preview, show it
  if (filePreview) {
    return (
      <div className="w-full space-y-4">
        {/* File Preview Card */}
        <div className="p-4 border rounded-lg bg-card space-y-4">
          {/* File Header */}
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className="p-2 rounded-md bg-primary/10 flex-shrink-0">
                <FileText className="w-5 h-5 text-primary" />
              </div>

              <div className="flex-1 min-w-0 space-y-2">
                {/* Filename */}
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium truncate" title={filePreview.file.name}>
                    {filePreview.file.name}
                  </p>
                  {!filePreview.validation.isValid && (
                    <span className="flex-shrink-0 px-2 py-0.5 text-xs font-medium rounded-full bg-destructive/10 text-destructive">
                      {t('doc.invalid')}
                    </span>
                  )}
                </div>

                {/* File Info Row */}
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  {/* File Type Badge */}
                  <span className="px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground">
                    {filePreview.fileTypeLabel}
                  </span>

                  {/* File Size */}
                  <span className="text-muted-foreground">
                    {formatFileSize(filePreview.file.size)} / {formatFileSize(MAX_FILE_SIZE)}
                  </span>

                  {/* Size Status Badge */}
                  {filePreview.sizeStatus === 'error' && (
                    <span className="px-2 py-0.5 rounded-md bg-destructive/10 text-destructive font-medium">
                      {t('doc.tooLarge')}
                    </span>
                  )}
                  {filePreview.sizeStatus === 'warning' && (
                    <span className="px-2 py-0.5 rounded-md bg-yellow-500/10 text-yellow-600 dark:text-yellow-500 font-medium">
                      {t('doc.largeFile')}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Clear Button */}
            {!isUploading && !isValidating && (
              <button
                onClick={handleClearPreview}
                className="flex-shrink-0 p-1 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                title={t('doc.removeFile')}
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Size Progress Bar */}
          <div className="space-y-1">
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className={cn(
                  'h-full transition-all duration-300 ease-out',
                  filePreview.sizeStatus === 'error' && 'bg-destructive',
                  filePreview.sizeStatus === 'warning' && 'bg-yellow-500',
                  filePreview.sizeStatus === 'ok' && 'bg-primary'
                )}
                style={{ width: `${filePreview.sizePercentage}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground text-right">
              {t('doc.percentOfLimit')} {filePreview.sizePercentage.toFixed(0)}%
            </p>
          </div>

          {/* Validation Errors */}
          {filePreview.validation.errors.length > 0 && (
            <div className="space-y-2 p-3 rounded-md bg-destructive/10 border border-destructive/20">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-destructive flex-shrink-0 mt-0.5" />
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium text-destructive">
                    {filePreview.validation.errors.length === 1
                      ? t('doc.error')
                      : `${filePreview.validation.errors.length}${t('doc.errors')}`}
                  </p>
                  <ul className="space-y-1">
                    {filePreview.validation.errors.map((error, index) => (
                      <li key={index} className="text-xs text-destructive">
                        • {error.message}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Validation Warnings */}
          {filePreview.validation.warnings.length > 0 && (
            <div className="space-y-2 p-3 rounded-md bg-yellow-500/10 border border-yellow-500/20">
              <div className="flex items-start gap-2">
                <FileWarning className="w-4 h-4 text-yellow-600 dark:text-yellow-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium text-yellow-600 dark:text-yellow-500">
                    {filePreview.validation.warnings.length === 1
                      ? t('doc.warning')
                      : `${filePreview.validation.warnings.length}${t('doc.warnings')}`}
                  </p>
                  <ul className="space-y-1">
                    {filePreview.validation.warnings.map((warning, index) => (
                      <li key={index} className="text-xs text-yellow-600 dark:text-yellow-500">
                        • {warning.message}
                      </li>
                    ))}
                  </ul>
                  {filePreview.validation.isValid && (
                    <button
                      onClick={() => onUpload(filePreview.file)}
                      className="text-xs font-medium text-yellow-600 dark:text-yellow-500 underline hover:no-underline"
                    >
                      {t('doc.uploadAnyway')}
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Upload Status */}
          {(isUploading || isValidating) && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              <span>{isValidating ? t('doc.validating') : t('doc.uploading')}</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Show dropzone
  return (
    <div
      {...getRootProps()}
      className={cn(
        'relative border-2 border-dashed rounded-lg p-8 transition-all duration-200 cursor-pointer',
        'hover:border-primary/50 hover:bg-primary/5',
        isDragActive && 'border-primary bg-primary/10',
        isDragReject && 'border-destructive bg-destructive/10',
        (isUploading || isValidating) && 'opacity-50 cursor-not-allowed',
        'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2'
      )}
    >
      <input {...(getInputProps() as React.InputHTMLAttributes<HTMLInputElement>)} />

      <div className="flex flex-col items-center justify-center gap-4 text-center">
        {isDragReject ? (
          <>
            <AlertCircle className="w-12 h-12 text-destructive" />
            <p className="text-destructive font-medium">{t('doc.fileTypeNotSupported')}</p>
          </>
        ) : (
          <>
            <div
              className={cn(
                'p-4 rounded-full transition-colors',
                isDragActive ? 'bg-primary/20' : 'bg-primary/10'
              )}
            >
              {isDragActive ? (
                <FileText className="w-8 h-8 text-primary" />
              ) : (
                <Upload className="w-8 h-8 text-primary" />
              )}
            </div>

            <div className="space-y-2">
              <p className="text-lg font-medium">
                {isDragActive
                  ? t('doc.dropHere')
                  : isUploading || isValidating
                  ? t('doc.processing')
                  : t('doc.dragDrop')}
              </p>
              <p className="text-sm text-muted-foreground">
                {isUploading || isValidating
                  ? t('doc.processWait')
                  : t('doc.clickSelect')}
              </p>
            </div>

            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">
                {t('doc.supported')}: {acceptedTypeLabels}
              </p>
              <p className="text-xs text-muted-foreground">
                {t('doc.maxSize')}: {formatFileSize(MAX_FILE_SIZE)}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
