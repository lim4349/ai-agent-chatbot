'use client';

import { useEffect, useState } from 'react';
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
import { DocumentList } from './document-list';
import { useDocumentStore } from '@/stores/document-store';
import { useChatStore, getDeviceId } from '@/stores/chat-store';
import { useToastStore } from '@/stores/toast-store';
import { useTranslation } from '@/lib/i18n';

export function CombinedDocumentUpload() {
  const [open, setOpen] = useState(false);
  const { t } = useTranslation();
  const { addToast } = useToastStore();
  const activeSessionId = useChatStore((state) => state.activeSessionId);

  const {
    documents,
    isUploading,
    isLoading,
    deletingDocumentIds,
    uploadProgress,
    uploadStatus,
    documentError,
    uploadFile,
    fetchDocuments,
    deleteDocument,
    resetUploadStatus,
  } = useDocumentStore();

  useEffect(() => {
    if (!open || !activeSessionId) return;
    const deviceId = getDeviceId();
    if (deviceId) {
      void fetchDocuments(deviceId, activeSessionId);
    }
  }, [activeSessionId, fetchDocuments, open]);

  const handleFileUpload = (file: File) => {
    // Get sessionId and deviceId
    const sessionId = activeSessionId;
    const deviceId = getDeviceId();

    if (!sessionId) {
      addToast(t('doc.noActiveSession'), 'error');
      return;
    }

    // Keep the dialog open so users can see progress and the new document row.
    uploadFile(file, sessionId, deviceId)
      .then(() => {
        const { uploadStatus, uploadError } = useDocumentStore.getState();
        if (uploadStatus === 'completed') {
          useChatStore.getState().markSessionSynced(sessionId);
          addToast(t('doc.uploadSuccess', file.name), 'success');
        } else if (uploadStatus === 'error') {
          addToast(uploadError || t('doc.uploadFailed'), 'error');
        }
      })
      .catch((error) => {
        addToast(error instanceof Error ? error.message : t('doc.uploadFailed'), 'error');
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
    if (!newOpen && !isUploading) {
      resetUploadStatus();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Upload className="w-4 h-4" />
          {isUploading ? t('doc.uploading') : t('doc.upload')}
        </Button>
      </DialogTrigger>
      <DialogContent className="w-[95%] max-w-[400px] sm:max-w-[550px]">
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
              filename={useDocumentStore.getState().currentUploadFilename || t('doc.unknownFile')}
            />
          )}

          <div className="space-y-2">
            <div>
              <h3 className="text-sm font-medium">{t('doc.listTitle')}</h3>
              <p className="text-xs text-muted-foreground">{t('doc.listDescription')}</p>
            </div>
            <DocumentList
              documents={documents}
              onDelete={(id) => deleteDocument(id, getDeviceId(), activeSessionId ?? undefined)}
              isLoading={isLoading}
              deletingDocumentIds={deletingDocumentIds}
              error={documentError}
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
