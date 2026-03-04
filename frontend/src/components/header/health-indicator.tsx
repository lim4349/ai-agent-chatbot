'use client';

import { useEffect, useState } from 'react';
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
import type { MetricsSummary } from '@/types';

export function HealthIndicator() {
  const { health, setHealth } = useChatStore();
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await api.getHealth();
        setHealth(data);
      } catch {
        setHealth(null);
      }
    };

    const fetchMetrics = async () => {
      try {
        const data = await api.getMetricsSummary('24h');
        setMetrics(data);
      } catch {
        setMetrics(null);
      }
    };

    // Initial check
    checkHealth();
    fetchMetrics();
    const interval = setInterval(checkHealth, HEALTH_CHECK_INTERVAL);
    const metricsInterval = setInterval(fetchMetrics, HEALTH_CHECK_INTERVAL * 2); // Less frequent for metrics

    // Pause polling when tab is hidden to save resources
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Tab is hidden, interval continues but we could reduce frequency
        // For now, we just let it run - the browser will throttle it
      } else {
        // Tab is visible again, check immediately
        checkHealth();
        fetchMetrics();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(interval);
      clearInterval(metricsInterval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [setHealth]);

  const isHealthy = health?.status === 'ok';

  // Daily quota from backend config (0 = unlimited, hide quota display)
  const dailyRequestLimit = health?.daily_request_limit ?? 0;
  const hasUsage = metrics && metrics.total_requests > 0 && dailyRequestLimit > 0;
  const requestsToday = hasUsage ? metrics.total_requests : 0;
  const usagePercent = dailyRequestLimit > 0 ? Math.min((requestsToday / dailyRequestLimit) * 100, 100) : 0;
  const remainingRequests = dailyRequestLimit > 0 ? Math.max(dailyRequestLimit - requestsToday, 0) : 0;

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
            {hasUsage && dailyRequestLimit > 0 && (
              <div className="border-t border-border my-2 pt-2">
                <p className="text-muted-foreground mb-1">{t('health.dailyQuota')}:</p>
                <p><strong>{t('health.requestsToday')}:</strong> {requestsToday}/{dailyRequestLimit}</p>
                <div className="w-full bg-muted rounded-full h-1.5 mt-1">
                  <div
                    className={cn(
                      'h-1.5 rounded-full transition-all',
                      usagePercent >= 90 ? 'bg-red-500' : usagePercent >= 70 ? 'bg-amber-500' : 'bg-green-500'
                    )}
                    style={{ width: `${usagePercent}%` }}
                  />
                </div>
                <p className="text-muted-foreground mt-1">{t('health.remaining')}: {remainingRequests}</p>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs">Backend unavailable</p>
        )}
      </TooltipContent>
    </Tooltip>
  );
}
