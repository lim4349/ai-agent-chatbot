'use client';

import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface ContextResetButtonProps {
  onReset: () => void;
  disabled?: boolean;
}

export function ContextResetButton({ onReset, disabled }: ContextResetButtonProps) {
  const [showDialog, setShowDialog] = useState(false);

  const handleConfirm = () => {
    onReset();
    setShowDialog(false);
  };

  return (
    <>
      <TooltipProvider delayDuration={0}>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => setShowDialog(true)}
              disabled={disabled}
            >
              <RefreshCw className="w-4 h-4" />
              새 주제로 시작
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>현재 대화 맥락을 초기화하고 새 주제로 시작합니다</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>새 주제로 시작하시겠습니까?</DialogTitle>
            <DialogDescription>
              현재 대화의 맥락이 초기화됩니다. 이전 대화는 요약되어 저장되지만,
              새로운 메시지는 이전 대화와 연결되지 않습니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              취소
            </Button>
            <Button onClick={handleConfirm}>
              확인
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
