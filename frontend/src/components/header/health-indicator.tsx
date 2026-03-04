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

  // Calculate RPM/TPM/RPD from 24h metrics
  const hasUsage = metrics && metrics.total_requests > 0;
  const rpm = hasUsage ? (metrics.total_requests / (24 * 60)).toFixed(2) : '0.00';
  const tpm = hasUsage ? (metrics.total_tokens / (24 * 60)).toFixed(1) : '0.0';
  const rpd = hasUsage ? metrics.total_requests.toLocaleString() : '0';

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
            {hasUsage && (
              <div className="border-t border-border my-2 pt-2">
                <p className="text-muted-foreground mb-1">{t('health.usage24h')}:</p>
                <p><strong>{t('health.rpm')}:</strong> {rpm}</p>
                <p><strong>{t('health.tpm')}:</strong> {tpm}</p>
                <p><strong>{t('health.rpd')}:</strong> {rpd}</p>
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
