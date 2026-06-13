'use client';

import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useTranslation } from '@/lib/i18n';
import { Bot } from 'lucide-react';

interface AgentBadgeProps {
  agent: string;
}

export function AgentBadge({ agent }: AgentBadgeProps) {
  const { t } = useTranslation();
  const label = agent === 'assistant' ? t('agent.assistant') : agent;

  return (
    <TooltipProvider delayDuration={100}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="secondary"
            className="bg-emerald-500/20 text-emerald-500 text-xs font-medium animate-in fade-in slide-in-from-left-2 duration-300"
          >
            <Bot className="w-3 h-3 mr-1" />
            {label}
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[200px]">
          <p className="font-medium">{label}</p>
          <p className="text-xs text-muted-foreground">{t('agent.assistantDescription')}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
