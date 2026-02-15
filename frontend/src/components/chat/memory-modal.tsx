'use client';

import * as React from 'react';
import { BrainIcon, XIcon, TrashIcon } from 'lucide-react';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';

export interface MemoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  memories: string[];
  onDeleteMemory?: (index: number) => void;
}

export function MemoryModal({
  isOpen,
  onClose,
  memories,
  onDeleteMemory,
}: MemoryModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BrainIcon className="h-5 w-5 text-purple-500" />
            저장된 기억
          </DialogTitle>
          <DialogDescription>
            AI가 기억하고 있는 정보 목록입니다
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[400px] pr-4">
          {memories.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <BrainIcon className="h-12 w-12 text-muted-foreground/30" />
              <p className="mt-4 text-sm text-muted-foreground">
                아직 저장된 기억이 없습니다
              </p>
              <p className="text-xs text-muted-foreground/70">
                &quot;기억해: 내용&quot; 형식으로 기억을 저장할 수 있습니다
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {memories.map((memory, index) => (
                <div
                  key={index}
                  className={cn(
                    'group flex items-start gap-3 rounded-lg border p-3',
                    'bg-muted/50 hover:bg-muted transition-colors'
                  )}
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                    {index + 1}
                  </span>
                  <p className="flex-1 text-sm">{memory}</p>
                  {onDeleteMemory && (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => onDeleteMemory(index)}
                      className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <TrashIcon className="h-4 w-4 text-destructive" />
                      <span className="sr-only">Delete memory</span>
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>

        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button variant="outline" onClick={onClose}>
            닫기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
