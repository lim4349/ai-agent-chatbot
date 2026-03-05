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
import type { MetricsSummary, RateLimitStatus } from '@/types';

function formatResetIn(resetAt: string): number {
  const now = Date.now();
  const reset = new Date(resetAt).getTime();
  return Math.max(0, Math.floor((reset - now) / 1000));
}

interface RateLimitRowProps {
  icon: string;
  label: string;
  status: RateLimitStatus;
  secondsLeft: number;
  resetInText: string;
  isToken?: boolean;
}

function RateLimitRow({ icon, label, status, secondsLeft, resetInText, isToken }: RateLimitRowProps) {
  const usagePercent = status.limit > 0 ? Math.min((status.used / status.limit) * 100, 100) : 0;
  const displayUsed = isToken ? formatTokens(status.used) : status.used;
  const displayLimit = isToken ? formatTokens(status.limit) : status.limit;

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="flex items-center gap-1 text-muted-foreground min-w-0">
          <span>{icon}</span>
          <span className="truncate">{label}</span>
        </span>
        <span className="shrink-0 font-mono">
          {displayUsed}/{displayLimit}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-muted rounded-full h-1">
          <div
            className={cn(
              'h-1 rounded-full transition-all',
              usagePercent >= 90 ? 'bg-red-500' : usagePercent >= 70 ? 'bg-amber-500' : 'bg-green-500'
            )}
            style={{ width: `${usagePercent}%` }}
          />
        </div>
        <span className="text-xs text-muted-foreground shrink-0 min-w-[60px] text-right">
          {secondsLeft <= 0 ? '...' : resetInText}
        </span>
      </div>
    </div>
  );
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return String(n);
}

export function HealthIndicator() {
  const { health, setHealth } = useChatStore();
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [isOpen, setIsOpen] = useState(false);

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
    const metricsInterval = setInterval(fetchMetrics, HEALTH_CHECK_INTERVAL * 2);

    // Pause polling when tab is hidden to save resources
    const handleVisibilityChange = () => {
      if (!document.hidden) {
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

  // 1-second interval to update countdown timers
  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(tick);
  }, []);

  const isHealthy = health?.status === 'ok';
  const rateLimitStatus = health?.rate_limit_status;

  // Quota limits from backend config (0 = unlimited, hide quota display)
  const dailyRequestLimit = health?.daily_request_limit ?? 0;
  const perMinuteLimit = health?.per_minute_limit ?? 0;
  const perHourLimit = health?.per_hour_limit ?? 0;
  const tokenLimit = health?.token_limit ?? 0;

  const hasUsage = metrics && metrics.total_requests > 0 && dailyRequestLimit > 0;
  const requestsToday = hasUsage ? metrics.total_requests : 0;
  const usagePercent = dailyRequestLimit > 0 ? Math.min((requestsToday / dailyRequestLimit) * 100, 100) : 0;
  const remainingRequests = dailyRequestLimit > 0 ? Math.max(dailyRequestLimit - requestsToday, 0) : 0;

  // Calculate seconds left for each limit from rate_limit_status
  const perMinuteSecondsLeft = rateLimitStatus?.per_minute
    ? Math.max(0, Math.floor((new Date(rateLimitStatus.per_minute.reset_at).getTime() - now) / 1000))
    : 0;
  const perHourSecondsLeft = rateLimitStatus?.per_hour
    ? Math.max(0, Math.floor((new Date(rateLimitStatus.per_hour.reset_at).getTime() - now) / 1000))
    : 0;
  const dailySecondsLeft = rateLimitStatus?.daily
    ? Math.max(0, Math.floor((new Date(rateLimitStatus.daily.reset_at).getTime() - now) / 1000))
    : 0;

  const hasRateLimitStatus = !!(
    rateLimitStatus?.per_minute ||
    rateLimitStatus?.per_hour ||
    rateLimitStatus?.daily
  );
  const hasLegacyLimits = !hasRateLimitStatus && (perMinuteLimit > 0 || perHourLimit > 0 || dailyRequestLimit > 0);

  const handleToggleTooltip = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsOpen(!isOpen);
  };

  // Close tooltip when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setIsOpen(false);
    if (isOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [isOpen]);

  return (
    <Tooltip open={isOpen} onOpenChange={setIsOpen}>
      <TooltipTrigger asChild>
        <div
          className="flex items-center gap-2 cursor-pointer"
          role="status"
          aria-live="polite"
          onClick={handleToggleTooltip}
        >
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
      <TooltipContent side="bottom" className="max-w-xs w-72">
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

            {/* Granular rate limit status from backend */}
            {hasRateLimitStatus && (
              <div className="border-t border-border mt-2 pt-2 space-y-2">
                {rateLimitStatus?.per_minute && (
                  <RateLimitRow
                    icon="⏱️"
                    label={t('health.perMinute')}
                    status={rateLimitStatus.per_minute}
                    secondsLeft={perMinuteSecondsLeft}
                    resetInText={t('health.resetsIn', perMinuteSecondsLeft)}
                  />
                )}
                {rateLimitStatus?.per_hour && (
                  <RateLimitRow
                    icon="🕐"
                    label={t('health.perHour')}
                    status={rateLimitStatus.per_hour}
                    secondsLeft={perHourSecondsLeft}
                    resetInText={t('health.resetsIn', perHourSecondsLeft)}
                  />
                )}
                {rateLimitStatus?.daily && (
                  <RateLimitRow
                    icon="📅"
                    label={t('health.dailyRequests')}
                    status={rateLimitStatus.daily}
                    secondsLeft={dailySecondsLeft}
                    resetInText={t('health.resetsIn', dailySecondsLeft)}
                  />
                )}
              </div>
            )}

            {/* Legacy fallback: show configured limits without real-time usage */}
            {hasLegacyLimits && (
              <div className="border-t border-border mt-2 pt-2 space-y-2">
                {(hasUsage || dailyRequestLimit > 0) && (
                  <div>
                    <p className="text-muted-foreground text-xs mb-1">📅 {t('health.dailyQuota')}:</p>
                    {dailyRequestLimit > 0 ? (
                      <>
                        <p className="text-xs"><strong>{t('health.requestsToday')}:</strong> {requestsToday}/{dailyRequestLimit}</p>
                        <div className="w-full bg-muted rounded-full h-1.5 mt-1">
                          <div
                            className={cn(
                              'h-1.5 rounded-full transition-all',
                              usagePercent >= 90 ? 'bg-red-500' : usagePercent >= 70 ? 'bg-amber-500' : 'bg-green-500'
                            )}
                            style={{ width: `${usagePercent}%` }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">{t('health.remaining')}: {remainingRequests}</p>
                      </>
                    ) : (
                      <p className="text-xs text-muted-foreground">{t('health.unlimited')}</p>
                    )}
                  </div>
                )}
                {perMinuteLimit > 0 && (
                  <div>
                    <p className="text-xs"><strong>⏱️ {t('health.perMinute')}:</strong> {perMinuteLimit} ({t('health.unlimited').toLowerCase() === 'unlimited' ? 'resets every minute' : '매 분 초기화'})</p>
                  </div>
                )}
                {perHourLimit > 0 && (
                  <div>
                    <p className="text-xs"><strong>🕐 {t('health.perHour')}:</strong> {perHourLimit} ({t('health.unlimited').toLowerCase() === 'unlimited' ? 'resets every hour' : '매 시간 초기화'})</p>
                  </div>
                )}
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
