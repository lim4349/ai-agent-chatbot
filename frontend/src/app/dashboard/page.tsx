'use client';

import { useCallback, useEffect, useState } from 'react';
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Header } from '@/components/header/header';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { useTranslation, type TranslationKey } from '@/lib/i18n';
import type { MetricsSummary, MetricsPeriod } from '@/types';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

// Agent color mapping for consistent theming
const AGENT_COLORS: Record<string, string> = {
  assistant: '#10b981',
  chat: '#3b82f6',       // Blue
  research: '#10b981',   // Green
};

// Nodes to exclude from legacy stats if older deployments recorded them.
const EXCLUDED_AGENTS = [
  'supervisor',
  'router',
  'code',
  'rag',
  'report',
  'web_search_collect',
  'retriever_collect',
];

const AGENT_LABEL_KEYS: Record<string, TranslationKey> = {
  assistant: 'agent.assistant',
  chat: 'agent.chat',
  research: 'agent.research',
};

const TOOL_LABEL_KEYS: Record<string, TranslationKey> = {
  web_search: 'tool.web_search',
  retriever: 'tool.retriever',
};

// Get agent color with fallback
function getAgentColor(agentName: string, index: number): string {
  return AGENT_COLORS[agentName] || COLORS[index % COLORS.length];
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

interface SummaryCardProps {
  title: string;
  value: string | number;
  description: string;
  color?: string;
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

  // Calculate success rate
  const successRate = metrics
    ? metrics.total_requests > 0
      ? ((metrics.successful_requests / metrics.total_requests) * 100).toFixed(1)
      : '0.0'
    : '0.0';

  // Filter out internal routing nodes from stats
  const filteredAgentStats = metrics?.agent_stats.filter(
    stat => !EXCLUDED_AGENTS.includes(stat.agent_name)
  ) || [];

  // Calculate total requests for percentage normalization
  const totalFilteredRequests = filteredAgentStats.reduce(
    (sum, stat) => sum + stat.total_requests, 0
  );

  // Prepare data for pie chart (requests by agent) with normalized percentages
  // Always ensure percentages sum to exactly 100%
  const pieData = (() => {
    if (filteredAgentStats.length === 0 || totalFilteredRequests === 0) return [];

    // Calculate raw percentages
    const rawPercentages = filteredAgentStats.map(stat => ({
      name: translatedLabel(stat.agent_name, AGENT_LABEL_KEYS, t),
      agentName: stat.agent_name,
      value: stat.total_requests,
      rawPercent: (stat.total_requests / totalFilteredRequests) * 100,
    }));

    // Round down all percentages
    const rounded = rawPercentages.map(item => ({
      ...item,
      percent: Math.floor(item.rawPercent),
    }));

    // Calculate the difference (remainder) to distribute
    const totalRounded = rounded.reduce((sum, item) => sum + item.percent, 0);
    let remainder = 100 - totalRounded;

    // Sort by decimal part (descending) to distribute remainder fairly
    const sortedByDecimal = [...rounded].sort((a, b) =>
      (b.rawPercent % 1) - (a.rawPercent % 1)
    );

    // Distribute remainder (1% each) to items with highest decimal parts
    for (let i = 0; i < sortedByDecimal.length && remainder > 0; i++) {
      const idx = rounded.findIndex(item => item.agentName === sortedByDecimal[i].agentName);
      if (idx !== -1) {
        rounded[idx].percent += 1;
        remainder -= 1;
      }
    }

    return rounded.map(({ name, agentName, value, percent }) => ({
      name,
      agentName,
      value,
      percent,
    }));
  })();

  // Prepare data for bar chart (requests by status)
  const statusData = metrics ? [
    { name: t('dashboard.success'), value: metrics.successful_requests, color: '#10b981' },
    { name: t('dashboard.failed'), value: metrics.failed_requests, color: '#ef4444' },
    { name: t('dashboard.blocked'), value: metrics.blocked_requests, color: '#f59e0b' },
  ] : [];

  // Prepare data for line chart (tokens by agent)
  const tokenData = filteredAgentStats.map(stat => ({
    name: translatedLabel(stat.agent_name, AGENT_LABEL_KEYS, t),
    agentName: stat.agent_name,
    tokens: stat.total_tokens,
  }));

  // Prepare data for duration chart
  const durationData = filteredAgentStats.map(stat => ({
    name: translatedLabel(stat.agent_name, AGENT_LABEL_KEYS, t),
    agentName: stat.agent_name,
    duration: Math.round(stat.avg_duration_ms),
  }));
  const evidenceRate = metrics?.quality_stats
    ? `${Math.round((metrics.quality_stats.evidence_rate || 0) * 100)}%`
    : '0%';
  const toolUsage = metrics?.quality_stats?.tool_counts
    ? Object.entries(metrics.quality_stats.tool_counts)
    : [];

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header onMenuClick={() => {}} />

      <div className="flex-1 overflow-auto p-6 bg-background">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold">{t('dashboard.title')}</h1>
              <p className="text-muted-foreground mt-1">
                {t('dashboard.description')}
              </p>
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
              {/* Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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

              {/* Charts Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Requests by Agent - Pie Chart */}
                <Card>
                  <CardHeader>
                    <CardTitle>{t('dashboard.requestsByAgent')}</CardTitle>
                    <CardDescription>{t('dashboard.requestsByAgentDescription')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {pieData.length > 0 ? (
                      <>
                        <ResponsiveContainer width="100%" height={260}>
                          <PieChart>
                            <Pie
                              data={pieData}
                              cx="50%"
                              cy="50%"
                              labelLine={false}
                              outerRadius={80}
                              fill="#8884d8"
                              dataKey="value"
                            >
                              {pieData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={getAgentColor(entry.agentName, index)} />
                              ))}
                            </Pie>
                            <Tooltip
                              formatter={(value) => [
                                Number(value).toLocaleString(),
                                t('dashboard.requests'),
                              ]}
                            />
                          </PieChart>
                        </ResponsiveContainer>
                        <div className="flex flex-wrap justify-center gap-3 text-xs text-muted-foreground">
                          {pieData.map((entry, index) => (
                            <div key={entry.agentName} className="flex items-center gap-1.5">
                              <span
                                className="h-2 w-2 rounded-full"
                                style={{ backgroundColor: getAgentColor(entry.agentName, index) }}
                              />
                              <span>{entry.name}</span>
                              <span className="font-medium text-foreground">{entry.percent}%</span>
                            </div>
                          ))}
                        </div>
                      </>
                    ) : (
                      <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                        {t('dashboard.noData')}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Request Status - Bar Chart */}
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
                        <YAxis />
                        <Tooltip
                          formatter={(value) => [
                            Number(value).toLocaleString(),
                            t('dashboard.requests'),
                          ]}
                        />
                        <Bar dataKey="value" fill="#3b82f6">
                          {statusData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              </div>

              {/* Tokens and Duration Charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Tokens by Agent */}
                <Card>
                  <CardHeader>
                    <CardTitle>{t('dashboard.tokensByAgent')}</CardTitle>
                    <CardDescription>{t('dashboard.tokensByAgentDescription')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {tokenData.length > 0 ? (
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={tokenData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip
                            formatter={(value) => [
                              Number(value).toLocaleString(),
                              t('dashboard.tokens'),
                            ]}
                          />
                          <Bar dataKey="tokens">
                            {tokenData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={getAgentColor(entry.agentName, index)} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                        {t('dashboard.noData')}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Avg Duration by Agent */}
                <Card>
                  <CardHeader>
                    <CardTitle>{t('dashboard.avgDurationByAgent')}</CardTitle>
                    <CardDescription>{t('dashboard.avgDurationByAgentDescription')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {durationData.length > 0 ? (
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={durationData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis tickFormatter={(value) => formatDuration(Number(value))} />
                          <Tooltip
                            formatter={(value) => [
                              formatDuration(Number(value)),
                              t('dashboard.duration'),
                            ]}
                          />
                          <Bar dataKey="duration">
                            {durationData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={getAgentColor(entry.agentName, index)} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                        {t('dashboard.noData')}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Agent Stats Table */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <SummaryCard
                  title={t('dashboard.evidenceRate')}
                  value={evidenceRate}
                  description={t('dashboard.evidenceRateDescription')}
                  color="text-emerald-500"
                />
                <SummaryCard
                  title={t('dashboard.evidenceTurns')}
                  value={metrics.quality_stats?.evidence_turns ?? 0}
                  description={t('dashboard.evidenceTurnsDescription')}
                  color="text-blue-500"
                />
                <SummaryCard
                  title={t('dashboard.noEvidenceTurns')}
                  value={metrics.quality_stats?.no_evidence_turns ?? 0}
                  description={t('dashboard.noEvidenceTurnsDescription')}
                  color="text-amber-500"
                />
              </div>

              {toolUsage.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>{t('dashboard.evidenceToolUsage')}</CardTitle>
                    <CardDescription>{t('dashboard.evidenceToolUsageDescription')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {toolUsage.map(([tool, count]) => (
                        <div
                          key={tool}
                          className="rounded-md border border-border px-3 py-2 text-sm"
                        >
                          <span className="font-medium">
                            {translatedLabel(tool, TOOL_LABEL_KEYS, t)}
                          </span>
                          <span className="ml-2 text-muted-foreground">{count}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardHeader>
                  <CardTitle>{t('dashboard.agentStatistics')}</CardTitle>
                  <CardDescription>{t('dashboard.agentStatisticsDescription')}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left p-2">{t('dashboard.agent')}</th>
                          <th className="text-right p-2">{t('dashboard.total')}</th>
                          <th className="text-right p-2">{t('dashboard.success')}</th>
                          <th className="text-right p-2">{t('dashboard.failed')}</th>
                          <th className="text-right p-2">{t('dashboard.blocked')}</th>
                          <th className="text-right p-2">{t('dashboard.avgDuration')}</th>
                          <th className="text-right p-2">{t('dashboard.tokens')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredAgentStats.map((stat, index) => {
                          const agentColor = getAgentColor(stat.agent_name, index);
                          return (
                          <tr
                            key={stat.agent_name}
                            className="border-b transition-all duration-200 hover:shadow-sm hover:border-l-2"
                            style={{ borderLeftColor: 'transparent' }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.borderLeftColor = agentColor;
                              e.currentTarget.style.backgroundColor = `${agentColor}08`;
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.borderLeftColor = 'transparent';
                              e.currentTarget.style.backgroundColor = 'transparent';
                            }}
                          >
                            <td className="p-2 font-medium flex items-center gap-2">
                              <span
                                className="w-2 h-2 rounded-full"
                                style={{ backgroundColor: agentColor }}
                              />
                              {translatedLabel(stat.agent_name, AGENT_LABEL_KEYS, t)}
                            </td>
                            <td className="text-right p-2">{stat.total_requests.toLocaleString()}</td>
                            <td className="text-right p-2 text-green-600">{stat.successful_requests.toLocaleString()}</td>
                            <td className="text-right p-2 text-red-600">{stat.failed_requests.toLocaleString()}</td>
                            <td className="text-right p-2 text-amber-600">{stat.blocked_requests.toLocaleString()}</td>
                            <td className="text-right p-2">{formatDuration(stat.avg_duration_ms)}</td>
                            <td className="text-right p-2">{stat.total_tokens.toLocaleString()}</td>
                          </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    {filteredAgentStats.length === 0 && (
                      <div className="text-center py-8 text-muted-foreground">
                        {t('dashboard.noAgentStats')}
                      </div>
                    )}
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
