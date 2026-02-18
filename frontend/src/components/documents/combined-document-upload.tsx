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
import { useChatStore, getDeviceId } from '@/stores/chat-store';
import { useToastStore } from '@/stores/toast-store';
import { useTranslation } from '@/lib/i18n';

export function CombinedDocumentUpload() {
  const [open, setOpen] = useState(false);
  const { t } = useTranslation();
  const { addToast } = useToastStore();

  const {
    isUploading,
    uploadProgress,
    uploadStatus,
    uploadError,
    uploadFile,
    resetUploadStatus,
  } = useDocumentStore();

  const handleFileUpload = async (file: File) => {
    // Get sessionId and deviceId
    const sessionId = useChatStore.getState().activeSessionId;
    const deviceId = getDeviceId();

    if (!sessionId) {
      addToast('No active session. Please create a session first.', 'error');
      return;
    }

    // Close modal immediately and upload in background
    setOpen(false);

    // Start background upload
    uploadFile(file, sessionId, deviceId)
      .then(() => {
        const { uploadStatus, uploadError } = useDocumentStore.getState();
        if (uploadStatus === 'completed') {
          addToast(`${file.name} uploaded successfully`, 'success');
        } else if (uploadStatus === 'error') {
          addToast(uploadError || 'Upload failed', 'error');
        }
      })
      .catch((error) => {
        addToast(error instanceof Error ? error.message : 'Upload failed', 'error');
      })
      .finally(() => {
        // Reset status after a delay
        setTimeout(() => {
          resetUploadStatus();
        }, 1000);
      });
  };

  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (!newOpen) {
      resetUploadStatus();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Upload className="w-4 h-4" />
          {isUploading ? 'Uploading...' : t('doc.upload')}
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

          {(uploadStatus === 'uploading' || uploadStatus === 'processing') && (
            <UploadProgress
              status={uploadStatus as 'uploading' | 'processing'}
              progress={uploadProgress}
              filename={useDocumentStore.getState().currentUploadFilename || 'Unknown file'}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
