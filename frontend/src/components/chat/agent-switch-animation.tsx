'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import {
  BookOpen,
  Code,
  Globe,
  MessageCircle,
  Route,
  type LucideIcon,
} from 'lucide-react';

interface AgentSwitchAnimationProps {
  fromAgent?: string;
  toAgent: string;
  isVisible: boolean;
}

const AGENT_ICONS: Record<string, LucideIcon> = {
  rag: BookOpen,
  code: Code,
  web_search: Globe,
  chat: MessageCircle,
  supervisor: Route,
};

const AGENT_COLORS: Record<string, string> = {
  rag: 'text-blue-500',
  code: 'text-purple-500',
  web_search: 'text-green-500',
  chat: 'text-gray-500',
  supervisor: 'text-orange-500',
};

const AGENT_LABELS: Record<string, string> = {
  rag: '문서 검색',
  code: '코드',
  web_search: '웹 검색',
  chat: '대화',
  supervisor: '라우터',
};

export function AgentSwitchAnimation({
  fromAgent,
  toAgent,
  isVisible,
}: AgentSwitchAnimationProps) {
  const [showAnimation, setShowAnimation] = useState(false);

  // Animation trigger requires setState - this is intentional for timed animation
  useEffect(() => {
    if (isVisible && fromAgent && fromAgent !== toAgent) {
      // Use requestAnimationFrame to avoid synchronous setState warning
      const rafId = requestAnimationFrame(() => {
        setShowAnimation(true);
      });
      const timer = setTimeout(() => {
        setShowAnimation(false);
      }, 1500);
      return () => {
        cancelAnimationFrame(rafId);
        clearTimeout(timer);
      };
    }
  }, [isVisible, fromAgent, toAgent]);

  if (!showAnimation || !fromAgent) return null;

  const FromIcon = AGENT_ICONS[fromAgent] || MessageCircle;
  const ToIcon = AGENT_ICONS[toAgent] || MessageCircle;
  const fromColor = AGENT_COLORS[fromAgent] || 'text-gray-500';
  const toColor = AGENT_COLORS[toAgent] || 'text-gray-500';
  const toLabel = AGENT_LABELS[toAgent] || toAgent;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted/50 border border-border/50 animate-in fade-in slide-in-from-left-2 duration-300">
      <div className="flex items-center gap-1.5">
        <FromIcon className={cn('w-3.5 h-3.5', fromColor)} />
        <span className="text-xs text-muted-foreground">→</span>
        <ToIcon className={cn('w-3.5 h-3.5', toColor)} />
      </div>
      <span className={cn('text-xs font-medium', toColor)}>
        {toLabel} 에이전트로 전환
      </span>
    </div>
  );
}
