'use client';

import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';
import { useTranslation } from '@/lib/i18n';

interface NewSessionButtonProps {
  onClick: () => void;
}

export function NewSessionButton({ onClick }: NewSessionButtonProps) {
  const { t } = useTranslation();

  return (
    <Button
      variant="outline"
      className="w-full justify-start gap-2"
      onClick={onClick}
    >
      <Plus className="w-4 h-4" />
      {t('sidebar.newChat')}
    </Button>
  );
}
