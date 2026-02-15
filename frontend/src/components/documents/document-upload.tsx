'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Upload, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useTranslation } from '@/lib/i18n';

export function DocumentUpload() {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const { t } = useTranslation();

  const handleUpload = async () => {
    if (!content.trim()) return;

    setLoading(true);
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
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Upload className="w-4 h-4" />
          {t('doc.upload')}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{t('doc.uploadTitle')}</DialogTitle>
          <DialogDescription>{t('doc.uploadDescription')}</DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <Textarea
            placeholder={t('doc.placeholder')}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="min-h-[200px]"
          />
        </div>

        {message && (
          <p
            className={`text-sm ${
              message.type === 'success' ? 'text-green-500' : 'text-destructive'
            }`}
          >
            {message.text}
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            {t('doc.cancel')}
          </Button>
          <Button onClick={handleUpload} disabled={loading || !content.trim()}>
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                {t('doc.uploading')}
              </>
            ) : (
              t('doc.uploadButton')
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
