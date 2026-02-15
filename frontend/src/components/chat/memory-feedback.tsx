'use client';

import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { SaveIcon, TrashIcon, FileTextIcon, BrainIcon, XIcon } from 'lucide-react';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import type { ParsedMemoryCommand } from '@/lib/memory-commands';

export interface MemoryFeedbackProps {
  command: ParsedMemoryCommand;
  onDismiss: () => void;
}

const feedbackConfig = {
  remember: {
    icon: SaveIcon,
    message: '정보를 저장했습니다',
    className: 'bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-200',
    iconClassName: 'text-blue-500 dark:text-blue-400',
  },
  recall: {
    icon: BrainIcon,
    message: '저장된 정보를 불러옵니다',
    className: 'bg-purple-50 border-purple-200 text-purple-800 dark:bg-purple-950 dark:border-purple-800 dark:text-purple-200',
    iconClassName: 'text-purple-500 dark:text-purple-400',
  },
  forget: {
    icon: TrashIcon,
    message: '정보를 삭제했습니다',
    className: 'bg-red-50 border-red-200 text-red-800 dark:bg-red-950 dark:border-red-800 dark:text-red-200',
    iconClassName: 'text-red-500 dark:text-red-400',
  },
  summarize: {
    icon: FileTextIcon,
    message: '대화를 요약했습니다',
    className: 'bg-green-50 border-green-200 text-green-800 dark:bg-green-950 dark:border-green-800 dark:text-green-200',
    iconClassName: 'text-green-500 dark:text-green-400',
  },
  none: null,
};

export function MemoryFeedback({ command, onDismiss }: MemoryFeedbackProps) {
  const config = feedbackConfig[command.type];

  if (!config) return null;

  const Icon = config.icon;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -10, scale: 0.95 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
        className={cn(
          'flex items-center gap-2 rounded-lg border px-4 py-2 shadow-sm',
          config.className
        )}
      >
        <Icon className={cn('h-4 w-4', config.iconClassName)} />
        <span className="text-sm font-medium">{config.message}</span>
        {command.content && (
          <span className="ml-2 max-w-[200px] truncate text-xs opacity-70">
            &quot;{command.content}&quot;
          </span>
        )}
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={onDismiss}
          className="ml-2 shrink-0 opacity-70 hover:opacity-100"
        >
          <XIcon className="h-3 w-3" />
          <span className="sr-only">Dismiss</span>
        </Button>
      </motion.div>
    </AnimatePresence>
  );
}
