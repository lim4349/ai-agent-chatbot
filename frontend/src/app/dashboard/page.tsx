'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Header } from '@/components/header/header';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { useTranslation, type TranslationKey } from '@/lib/i18n';
import type { MetricsPeriod, MetricsSummary } from '@/types';

const STATUS_COLORS = {
  success: '#10b981',
  failed: '#ef4444',
  blocked: '#f59e0b',
};

const QUALITY_COLORS = {
  evidence: '#10b981',
  noEvidence: '#f59e0b',
};

const TOOL_COLORS = ['#14b8a6', '#60a5fa', '#a78bfa', '#f59e0b', '#ec4899'];

const CONFIDENCE_COLORS: Record<string, string> = {
  high: '#10b981',
  medium: '#60a5fa',
  low: '#f59e0b',
  none: '#6b7280',
  error: '#ef4444',
};

const TOOL_LABEL_KEYS: Record<string, TranslationKey> = {
  web_search: 'tool.web_search',
  retriever: 'tool.retriever',
};

const CONFIDENCE_LABEL_KEYS: Record<string, TranslationKey> = {
  high: 'confidence.high',
  medium: 'confidence.medium',
  low: 'confidence.low',
  none: 'confidence.none',
  error: 'confidence.error',
};

interface SummaryCardProps {
  title: string;
  value: string | number;
  description: string;
  color?: string;
}

interface MetricRowProps {
  label: string;
  value: string | number;
  color?: string;
}

function formatDuration(durationMs: number): string {
  if (durationMs >= 1000) {
    return `${(durationMs / 1000).toFixed(durationMs >= 10000 ? 1 : 2)}s`;
  }
  return `${Math.round(durationMs)}ms`;
}

function translatedLabel(
  name: string,
  labels: Record<string, TranslationKey>,
  t: (key: TranslationKey, ...args: unknown[]) => string
): string {
  const key = labels[name];
  return key ? t(key) : name;
}

function SummaryCard({ title, value, description, color = 'text-primary' }: SummaryCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{title}</CardDescription>
        <CardTitle className={`text-3xl ${color}`}>{value}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

function MetricRow({ label, value, color = 'text-foreground' }: MetricRowProps) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border/60 py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`text-sm font-semibold ${color}`}>{value}</span>
    </div>
  );
}

export default function DashboardPage() {
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<MetricsPeriod>('24h');

  const loadMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMetricsSummary(period);
      setMetrics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load metrics');
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  const successRate = metrics
    ? metrics.total_requests > 0
      ? ((metrics.successful_requests / metrics.total_requests) * 100).toFixed(1)
      : '0.0'
    : '0.0';

  const evidenceTurns = metrics?.quality_stats?.evidence_turns ?? 0;
  const noEvidenceTurns = metrics?.quality_stats?.no_evidence_turns ?? 0;
  const evidenceRate = metrics?.quality_stats
    ? `${Math.round((metrics.quality_stats.evidence_rate || 0) * 100)}%`
    : '0%';

  const statusData = metrics ? [
    {
      name: t('dashboard.success'),
      value: metrics.successful_requests,
      color: STATUS_COLORS.success,
    },
    {
      name: t('dashboard.failed'),
      value: metrics.failed_requests,
      color: STATUS_COLORS.failed,
    },
    {
      name: t('dashboard.blocked'),
      value: metrics.blocked_requests,
      color: STATUS_COLORS.blocked,
    },
  ] : [];

  const evidenceData = [
    {
      name: t('dashboard.evidenceTurns'),
      value: evidenceTurns,
      color: QUALITY_COLORS.evidence,
    },
    {
      name: t('dashboard.noEvidenceTurns'),
      value: noEvidenceTurns,
      color: QUALITY_COLORS.noEvidence,
    },
  ];

  const toolUsageData = Object.entries(metrics?.quality_stats?.tool_counts ?? {}).map(
    ([tool, count], index) => ({
      name: translatedLabel(tool, TOOL_LABEL_KEYS, t),
      value: count,
      color: TOOL_COLORS[index % TOOL_COLORS.length],
    })
  );

  const confidenceData = Object.entries(metrics?.quality_stats?.confidence_counts ?? {}).map(
    ([confidence, count]) => ({
      name: translatedLabel(confidence, CONFIDENCE_LABEL_KEYS, t),
      value: count,
      color: CONFIDENCE_COLORS[confidence] ?? '#6b7280',
    })
  );

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header onMenuClick={() => {}} />

      <div className="flex-1 overflow-auto bg-background p-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold">{t('dashboard.title')}</h1>
              <p className="mt-1 text-muted-foreground">{t('dashboard.description')}</p>
            </div>
            <div className="flex gap-2">
              <Button
                variant={period === '24h' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setPeriod('24h')}
              >
                24H
              </Button>
              <Button
                variant={period === '7d' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setPeriod('7d')}
              >
                7D
              </Button>
              <Button
                variant={period === '30d' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setPeriod('30d')}
              >
                30D
              </Button>
            </div>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="text-muted-foreground">{t('dashboard.loading')}</div>
            </div>
          )}

          {error && (
            <Card className="border-destructive">
              <CardContent className="pt-6">
                <p className="text-destructive">{t('dashboard.error')}: {error}</p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-4"
                  onClick={loadMetrics}
                >
                  {t('dashboard.retry')}
                </Button>
              </CardContent>
            </Card>
          )}

          {metrics && !loading && (
            <>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                <SummaryCard
                  title={t('dashboard.totalRequests')}
                  value={metrics.total_requests.toLocaleString()}
                  description={`${t('dashboard.period')}: ${period}`}
                  color="text-blue-500"
                />
                <SummaryCard
                  title={t('dashboard.successRate')}
                  value={`${successRate}%`}
                  description={`${metrics.successful_requests.toLocaleString()} / ${metrics.total_requests.toLocaleString()}`}
                  color="text-green-500"
                />
                <SummaryCard
                  title={t('dashboard.avgDuration')}
                  value={formatDuration(metrics.avg_duration_ms)}
                  description={t('dashboard.avgResponseTime')}
                  color="text-amber-500"
                />
                <SummaryCard
                  title={t('dashboard.totalTokens')}
                  value={metrics.total_tokens.toLocaleString()}
                  description={t('dashboard.tokensProcessed')}
                  color="text-purple-500"
                />
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <SummaryCard
                  title={t('dashboard.evidenceRate')}
                  value={evidenceRate}
                  description={t('dashboard.evidenceRateDescription')}
                  color="text-emerald-500"
                />
                <SummaryCard
                  title={t('dashboard.evidenceTurns')}
                  value={evidenceTurns.toLocaleString()}
                  description={t('dashboard.evidenceTurnsDescription')}
                  color="text-blue-500"
                />
                <SummaryCard
                  title={t('dashboard.noEvidenceTurns')}
                  value={noEvidenceTurns.toLocaleString()}
                  description={t('dashboard.noEvidenceTurnsDescription')}
                  color="text-amber-500"
                />
              </div>

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>{t('dashboard.requestStatus')}</CardTitle>
                    <CardDescription>{t('dashboard.requestStatusDescription')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={statusData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis allowDecimals={false} />
                        <Tooltip
                          formatter={(value) => [
                            Number(value).toLocaleString(),
                            t('dashboard.requests'),
                          ]}
                        />
                        <Bar dataKey="value">
                          {statusData.map((entry) => (
                            <Cell key={entry.name} fill={entry.color} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>{t('dashboard.evidenceOverview')}</CardTitle>
                    <CardDescription>{t('dashboard.evidenceOverviewDescription')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={evidenceData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis allowDecimals={false} />
                        <Tooltip
                          formatter={(value) => [
                            Number(value).toLocaleString(),
                            t('dashboard.responses'),
                          ]}
                        />
                        <Bar dataKey="value">
                          {evidenceData.map((entry) => (
                            <Cell key={entry.name} fill={entry.color} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              </div>

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>{t('dashboard.evidenceToolUsage')}</CardTitle>
                    <CardDescription>{t('dashboard.evidenceToolUsageDescription')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {toolUsageData.length > 0 ? (
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={toolUsageData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis allowDecimals={false} />
                          <Tooltip
                            formatter={(value) => [
                              Number(value).toLocaleString(),
                              t('dashboard.calls'),
                            ]}
                          />
                          <Bar dataKey="value">
                            {toolUsageData.map((entry) => (
                              <Cell key={entry.name} fill={entry.color} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex h-[300px] items-center justify-center text-center text-sm text-muted-foreground">
                        {t('dashboard.noToolUsage')}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>{t('dashboard.confidenceDistribution')}</CardTitle>
                    <CardDescription>{t('dashboard.confidenceDistributionDescription')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {confidenceData.length > 0 ? (
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={confidenceData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis allowDecimals={false} />
                          <Tooltip
                            formatter={(value) => [
                              Number(value).toLocaleString(),
                              t('dashboard.responses'),
                            ]}
                          />
                          <Bar dataKey="value">
                            {confidenceData.map((entry) => (
                              <Cell key={entry.name} fill={entry.color} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex h-[300px] items-center justify-center text-center text-sm text-muted-foreground">
                        {t('dashboard.noConfidenceData')}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>{t('dashboard.assistantSummary')}</CardTitle>
                  <CardDescription>{t('dashboard.assistantSummaryDescription')}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 gap-x-8 md:grid-cols-2">
                    <MetricRow
                      label={t('dashboard.totalRequests')}
                      value={metrics.total_requests.toLocaleString()}
                    />
                    <MetricRow
                      label={t('dashboard.success')}
                      value={metrics.successful_requests.toLocaleString()}
                      color="text-green-500"
                    />
                    <MetricRow
                      label={t('dashboard.failed')}
                      value={metrics.failed_requests.toLocaleString()}
                      color="text-red-500"
                    />
                    <MetricRow
                      label={t('dashboard.blocked')}
                      value={metrics.blocked_requests.toLocaleString()}
                      color="text-amber-500"
                    />
                    <MetricRow
                      label={t('dashboard.avgDuration')}
                      value={formatDuration(metrics.avg_duration_ms)}
                    />
                    <MetricRow
                      label={t('dashboard.totalTokens')}
                      value={metrics.total_tokens.toLocaleString()}
                    />
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
