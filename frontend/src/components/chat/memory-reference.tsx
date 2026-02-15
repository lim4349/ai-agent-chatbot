'use client';

import { History } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';

interface MemoryReferenceProps {
  hasMemoryReference: boolean;
  referencedTopics?: string[];
}

export function MemoryReference({
  hasMemoryReference,
  referencedTopics,
}: MemoryReferenceProps) {
  if (!hasMemoryReference) return null;

  return (
    <TooltipProvider delayDuration={100}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="outline"
            className="text-xs font-normal bg-amber-500/10 text-amber-600 border-amber-500/20 hover:bg-amber-500/20 cursor-help animate-in fade-in duration-300"
          >
            <History className="w-3 h-3 mr-1" />
            이전 대화 참조
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[250px]">
          <div className="space-y-1">
            <p className="font-medium">이전 대화 참조됨</p>
            {referencedTopics && referencedTopics.length > 0 ? (
              <div className="text-xs text-muted-foreground">
                <p className="mb-1">참조된 주제:</p>
                <ul className="list-disc list-inside space-y-0.5">
                  {referencedTopics.map((topic, idx) => (
                    <li key={idx}>{topic}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                이전 대화 맥락을 참조하여 응답했습니다
              </p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
