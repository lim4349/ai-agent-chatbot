'use client';

import { useEffect } from 'react';
import { useChatStore } from '@/stores/chat-store';
import { api } from '@/lib/api';
import { HEALTH_CHECK_INTERVAL } from '@/lib/constants';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/lib/i18n';

export function HealthIndicator() {
  const { health, setHealth } = useChatStore();
  const { t } = useTranslation();

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await api.getHealth();
        setHealth(data);
      } catch {
        setHealth(null);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, HEALTH_CHECK_INTERVAL);
    return () => clearInterval(interval);
  }, [setHealth]);

  const isHealthy = health?.status === 'ok';

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-2 cursor-pointer" role="status" aria-live="polite">
          <div
            className={cn(
              'w-2.5 h-2.5 rounded-full',
              isHealthy ? 'bg-green-500' : 'bg-red-500'
            )}
            aria-hidden="true"
          />
          <span className="text-sm text-muted-foreground hidden sm:inline">
            {isHealthy ? t('health.connected') : t('health.disconnected')}
          </span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-xs">
        {health ? (
          <div className="space-y-1 text-xs">
            <p>
              <strong>Provider:</strong> {health.llm_provider}
            </p>
            <p>
              <strong>Model:</strong> {health.llm_model}
            </p>
            <p>
              <strong>Memory:</strong> {health.memory_backend}
            </p>
            <p>
              <strong>Agents:</strong> {health.available_agents.join(', ')}
            </p>
          </div>
        ) : (
          <p className="text-xs">Backend unavailable</p>
        )}
      </TooltipContent>
    </Tooltip>
  );
}
