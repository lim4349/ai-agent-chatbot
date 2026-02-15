'use client';

import { cn } from '@/lib/utils';
import { MessageSquare, FileText, AlertCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface MemoryIndicatorProps {
  messageCount: number;
  tokenCount?: number;
  isSummarized: boolean;
  lastSummaryTime?: string;
}

const MAX_MESSAGES_BEFORE_WARNING = 10;
const MAX_TOKENS_ESTIMATE = 4000;

export function MemoryIndicator({
  messageCount,
  tokenCount,
  isSummarized,
  lastSummaryTime,
}: MemoryIndicatorProps) {
  const showWarning = messageCount > MAX_MESSAGES_BEFORE_WARNING;
  const tokenPercentage = tokenCount
    ? Math.min((tokenCount / MAX_TOKENS_ESTIMATE) * 100, 100)
    : 0;

  return (
    <TooltipProvider delayDuration={0}>
      <div className="flex flex-col gap-2 p-3 bg-muted/50 rounded-lg border border-border/50">
        {/* Message count and summary badge */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium">
              {messageCount}개 메시지
            </span>
            {showWarning && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <AlertCircle className="w-4 h-4 text-amber-500" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>대화가 길어지고 있습니다. 새 주제로 시작하세요.</p>
                </TooltipContent>
              </Tooltip>
            )}
          </div>
          {isSummarized && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="secondary" className="text-xs gap-1">
                  <FileText className="w-3 h-3" />
                  요약됨
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                <p>이전 대화가 요약되었습니다</p>
                {lastSummaryTime && (
                  <p className="text-xs text-muted-foreground">
                    {new Date(lastSummaryTime).toLocaleTimeString()}
                  </p>
                )}
              </TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Token usage bar */}
        {tokenCount !== undefined && (
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>토큰 사용량</span>
              <span>{tokenCount.toLocaleString()}</span>
            </div>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full transition-all duration-300',
                  tokenPercentage > 80
                    ? 'bg-destructive'
                    : tokenPercentage > 50
                      ? 'bg-amber-500'
                      : 'bg-primary'
                )}
                style={{ width: `${tokenPercentage}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
