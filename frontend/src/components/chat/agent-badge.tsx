'use client';

import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { AgentType } from '@/types';
import { useTranslation, type TranslationKey } from '@/lib/i18n';
import {
  MessageCircle,
  Search,
  type LucideIcon,
} from 'lucide-react';

interface AgentBadgeProps {
  agent: AgentType | string;
  agents?: string[];  // All agents involved in the workflow
}

const AGENT_I18N_KEYS: Record<string, TranslationKey> = {
  chat: 'agent.chat',
  research: 'agent.research',
};

const AGENT_CONFIG: Record<string, {
  icon: LucideIcon;
  color: string;
  label: string;
  description: string;
}> = {
  chat: {
    icon: MessageCircle,
    color: 'bg-gray-500',
    label: '대화',
    description: '일반 대화'
  },
  research: {
    icon: Search,
    color: 'bg-blue-500',
    label: '리서치',
    description: '웹 검색과 업로드 문서 검색'
  },
};

export function AgentBadge({ agent, agents }: AgentBadgeProps) {
  const { t } = useTranslation();
  const config = AGENT_CONFIG[agent] || AGENT_CONFIG.chat;
  const Icon = config.icon;

  const i18nKey = AGENT_I18N_KEYS[agent];
  const label = i18nKey ? t(i18nKey) : config.label;

  // Calculate additional agents count (excluding the main agent)
  const additionalCount = agents && agents.length > 1
    ? agents.filter(a => a !== agent).length
    : 0;

  // Get labels for additional agents for tooltip
  const additionalAgentLabels = agents && agents.length > 1
    ? agents
        .filter(a => a !== agent)
        .map(a => {
          const agentConfig = AGENT_CONFIG[a];
          const agentI18nKey = AGENT_I18N_KEYS[a];
          return agentI18nKey ? t(agentI18nKey) : (agentConfig?.label || a);
        })
    : [];

  return (
    <TooltipProvider delayDuration={100}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="secondary"
            className={`${config.color}/20 ${config.color.replace('bg-', 'text-')} text-xs font-medium animate-in fade-in slide-in-from-left-2 duration-300`}
          >
            <Icon className="w-3 h-3 mr-1" />
            {label}
            {additionalCount > 0 && (
              <span className="ml-1 px-1 rounded bg-black/10 text-[10px]">
                +{additionalCount}
              </span>
            )}
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[200px]">
          <p className="font-medium">{label}</p>
          <p className="text-xs text-muted-foreground">{config.description}</p>
          {additionalAgentLabels.length > 0 && (
            <p className="text-xs text-muted-foreground mt-1 pt-1 border-t border-border">
              {t('agent.additionalAgents') || '추가 에이전트'}: {additionalAgentLabels.join(', ')}
            </p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
