'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Upload } from 'lucide-react';
import { FileUploadZone } from './file-upload-zone';
import { UploadProgress } from './upload-progress';
import { useDocumentStore } from '@/stores/document-store';
import { useTranslation } from '@/lib/i18n';

export function CombinedDocumentUpload() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const { t } = useTranslation();

  const {
    isUploading,
    uploadProgress,
    uploadStatus,
    uploadError,
    uploadFile,
    resetUploadStatus,
  } = useDocumentStore();

  const handleFileUpload = async (file: File) => {
    setMessage(null);
    try {
      await uploadFile(file);

      // Only close modal if upload was successful
      // Check uploadStatus from store after uploadFile completes
      const { uploadStatus, uploadError } = useDocumentStore.getState();

      if (uploadStatus === 'completed') {
        setMessage({ type: 'success', text: `Successfully uploaded ${file.name}` });
        setTimeout(() => {
          setOpen(false);
          resetUploadStatus();
          setMessage(null);
        }, 1500);
      } else if (uploadStatus === 'error') {
        setMessage({
          type: 'error',
          text: uploadError || 'Upload failed',
        });
      }
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Upload failed',
      });
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (!newOpen) {
      resetUploadStatus();
      setMessage(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Upload className="w-4 h-4" />
          {t('doc.upload')}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[550px]">
        <DialogHeader>
          <DialogTitle>{t('doc.uploadTitle')}</DialogTitle>
          <DialogDescription>{t('doc.uploadDescription')}</DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-4">
          <FileUploadZone
            onUpload={handleFileUpload}
            isUploading={isUploading}
          />

          {(uploadStatus === 'uploading' || uploadStatus === 'processing' || uploadStatus === 'completed' || uploadStatus === 'error') && (
            <UploadProgress
              status={uploadStatus as 'uploading' | 'processing' | 'completed' | 'error'}
              progress={uploadProgress}
              filename={useDocumentStore.getState().currentUploadFilename || 'Unknown file'}
              error={uploadError || undefined}
            />
          )}
        </div>

        {message && (
          <p
            className={`text-sm text-center ${
              message.type === 'success' ? 'text-green-500' : 'text-destructive'
            }`}
          >
            {message.text}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
