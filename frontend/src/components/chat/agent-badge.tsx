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
  BookOpen,
  Code,
  Globe,
  MessageCircle,
  Route,
  type LucideIcon,
} from 'lucide-react';

interface AgentBadgeProps {
  agent: AgentType | string;
}

const AGENT_I18N_KEYS: Record<string, TranslationKey> = {
  chat: 'agent.chat',
  code: 'agent.code',
  rag: 'agent.rag',
  web_search: 'agent.web_search',
  supervisor: 'agent.supervisor',
};

const AGENT_CONFIG: Record<string, {
  icon: LucideIcon;
  color: string;
  label: string;
  description: string;
}> = {
  rag: {
    icon: BookOpen,
    color: 'bg-blue-500',
    label: '문서 검색',
    description: '업로드된 문서에서 검색'
  },
  code: {
    icon: Code,
    color: 'bg-purple-500',
    label: '코드',
    description: '코드 생성 및 분석'
  },
  web_search: {
    icon: Globe,
    color: 'bg-green-500',
    label: '웹 검색',
    description: '실시간 웹 정보 검색'
  },
  chat: {
    icon: MessageCircle,
    color: 'bg-gray-500',
    label: '대화',
    description: '일반 대화'
  },
  supervisor: {
    icon: Route,
    color: 'bg-orange-500',
    label: '라우터',
    description: '요청 분석 및 라우팅'
  },
};

export function AgentBadge({ agent }: AgentBadgeProps) {
  const { t } = useTranslation();
  const config = AGENT_CONFIG[agent] || AGENT_CONFIG.chat;
  const Icon = config.icon;

  const i18nKey = AGENT_I18N_KEYS[agent];
  const label = i18nKey ? t(i18nKey) : config.label;

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
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[200px]">
          <p className="font-medium">{label}</p>
          <p className="text-xs text-muted-foreground">{config.description}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
