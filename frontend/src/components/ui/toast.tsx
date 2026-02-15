'use client';

import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { XIcon, CheckCircleIcon, InfoIcon, AlertTriangleIcon, XCircleIcon } from 'lucide-react';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

export type ToastType = 'success' | 'info' | 'warning' | 'error';

export interface ToastProps {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
  onClose: () => void;
}

const toastIcons = {
  success: CheckCircleIcon,
  info: InfoIcon,
  warning: AlertTriangleIcon,
  error: XCircleIcon,
};

const toastStyles = {
  success: 'bg-green-50 border-green-200 text-green-800 dark:bg-green-950 dark:border-green-800 dark:text-green-200',
  info: 'bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-200',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800 dark:bg-yellow-950 dark:border-yellow-800 dark:text-yellow-200',
  error: 'bg-red-50 border-red-200 text-red-800 dark:bg-red-950 dark:border-red-800 dark:text-red-200',
};

const iconStyles = {
  success: 'text-green-500 dark:text-green-400',
  info: 'text-blue-500 dark:text-blue-400',
  warning: 'text-yellow-500 dark:text-yellow-400',
  error: 'text-red-500 dark:text-red-400',
};

export function Toast({ message, type, onClose }: ToastProps) {
  const Icon = toastIcons[type];

  return (
    <motion.div
      initial={{ opacity: 0, y: 50, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={cn(
        'pointer-events-auto flex w-full max-w-sm items-center gap-3 rounded-lg border p-4 shadow-lg',
        toastStyles[type]
      )}
    >
      <Icon className={cn('h-5 w-5 shrink-0', iconStyles[type])} />
      <p className="flex-1 text-sm font-medium">{message}</p>
      <Button
        variant="ghost"
        size="icon-xs"
        onClick={onClose}
        className="shrink-0 opacity-70 hover:opacity-100"
      >
        <XIcon className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </Button>
    </motion.div>
  );
}

export interface ToastContainerProps {
  children: React.ReactNode;
}

export function ToastContainer({ children }: ToastContainerProps) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      <AnimatePresence mode="popLayout">
        {children}
      </AnimatePresence>
    </div>
  );
}
