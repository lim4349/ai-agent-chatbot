import { create } from 'zustand';
import { v4 as uuidv4 } from 'uuid';

export type ToastType = 'success' | 'info' | 'warning' | 'error';

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration: number;
}

interface ToastStore {
  toasts: Toast[];
  addToast: (message: string, type: ToastType, duration?: number) => void;
  removeToast: (id: string) => void;
  clearAllToasts: () => void;
}

const DEFAULT_DURATION = 3000;
const MIN_DURATION = 2000;
const MAX_DURATION = 8000;

function calculateDuration(message: string): number {
  const length = message.length;

  if (length <= 30) {
    return 2000; // 짧음: 2초
  } else if (length <= 80) {
    return 3000; // 중간: 3초
  } else {
    return Math.min(5000 + (length - 80) * 50, MAX_DURATION); // 김: 5초 + 초과분당 50ms, 최대 8초
  }
}

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],

  addToast: (message, type, duration) => {
    const id = uuidv4();
    const actualDuration = duration ?? calculateDuration(message);
    const toast: Toast = {
      id,
      message,
      type,
      duration: actualDuration,
    };

    set((state) => ({
      toasts: [...state.toasts, toast],
    }));

    // Auto-remove toast after duration
    if (actualDuration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }));
      }, actualDuration);
    }
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }));
  },

  clearAllToasts: () => {
    set({ toasts: [] });
  },
}));
