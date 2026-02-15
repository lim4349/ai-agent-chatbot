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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Upload, FileText, Loader2 } from 'lucide-react';
import { FileUploadZone } from './file-upload-zone';
import { UploadProgress } from './upload-progress';
import { useDocumentStore } from '@/stores/document-store';
import { api } from '@/lib/api';
import { useTranslation } from '@/lib/i18n';

export function CombinedDocumentUpload() {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('file');
  const [content, setContent] = useState('');
  const [textUploadLoading, setTextUploadLoading] = useState(false);
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
      setMessage({ type: 'success', text: `Successfully uploaded ${file.name}` });
      setTimeout(() => {
        setOpen(false);
        resetUploadStatus();
        setMessage(null);
      }, 1500);
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Upload failed',
      });
    }
  };

  const handleTextUpload = async () => {
    if (!content.trim()) return;

    setTextUploadLoading(true);
    setMessage(null);

    try {
      const response = await api.uploadDocument({ content: content.trim() });
      setMessage({ type: 'success', text: response.message });
      setContent('');
      setTimeout(() => {
        setOpen(false);
        setMessage(null);
      }, 1500);
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Upload failed',
      });
    } finally {
      setTextUploadLoading(false);
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (!newOpen) {
      resetUploadStatus();
      setMessage(null);
      setContent('');
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

        <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-4">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="file" className="gap-2">
              <FileText className="w-4 h-4" />
              {t('doc.uploadFile')}
            </TabsTrigger>
            <TabsTrigger value="text" className="gap-2">
              <Upload className="w-4 h-4" />
              {t('doc.pasteText')}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="file" className="mt-4 space-y-4">
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
          </TabsContent>

          <TabsContent value="text" className="mt-4 space-y-4">
            <Textarea
              placeholder={t('doc.placeholder')}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="min-h-[200px]"
              disabled={textUploadLoading}
            />

            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setOpen(false)}
                disabled={textUploadLoading}
              >
                {t('doc.cancel')}
              </Button>
              <Button
                onClick={handleTextUpload}
                disabled={textUploadLoading || !content.trim()}
              >
                {textUploadLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    {t('doc.uploading')}
                  </>
                ) : (
                  t('doc.uploadButton')
                )}
              </Button>
            </div>
          </TabsContent>
        </Tabs>

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
