'use client';

import { useEffect, useState } from 'react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Header } from '@/components/header/header';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { useTranslation } from '@/lib/i18n';
import type { MetricsSummary, MetricsPeriod, AgentMetricItem } from '@/types';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

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

  useEffect(() => {
    loadMetrics();
  }, [period]);

  const loadMetrics = async () => {
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
  };

  // Calculate success rate
  const successRate = metrics
    ? metrics.total_requests > 0
      ? ((metrics.successful_requests / metrics.total_requests) * 100).toFixed(1)
      : '0.0'
    : '0.0';

  // Prepare data for pie chart (requests by agent)
  const pieData = metrics?.agent_stats.map(stat => ({
    name: stat.agent_name,
    value: stat.total_requests,
  })) || [];

  // Prepare data for bar chart (requests by status)
  const statusData = metrics ? [
    { name: t('dashboard.success'), value: metrics.successful_requests, color: '#10b981' },
    { name: t('dashboard.failed'), value: metrics.failed_requests, color: '#ef4444' },
    { name: t('dashboard.blocked'), value: metrics.blocked_requests, color: '#f59e0b' },
  ] : [];

  // Prepare data for line chart (tokens by agent)
  const tokenData = metrics?.agent_stats.map(stat => ({
    name: stat.agent_name,
    tokens: stat.total_tokens,
  })) || [];

  // Prepare data for duration chart
  const durationData = metrics?.agent_stats.map(stat => ({
    name: stat.agent_name,
    duration: Math.round(stat.avg_duration_ms),
  })) || [];

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header onMenuClick={() => {}} />

      <div className="flex-1 overflow-auto p-6 bg-background">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
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
                  description={`${metrics.successful_requests} ${t('dashboard.of')} ${metrics.total_requests}`}
                  color="text-green-500"
                />
                <SummaryCard
                  title={t('dashboard.avgDuration')}
                  value={`${Math.round(metrics.avg_duration_ms)}ms`}
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
                      <ResponsiveContainer width="100%" height={300}>
                        <PieChart>
                          <Pie
                            data={pieData}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({ name, percent }) => `${name}: ${((percent ?? 0) * 100).toFixed(0)}%`}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="value"
                          >
                            {pieData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip />
                        </PieChart>
                      </ResponsiveContainer>
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
                        <Tooltip />
                        <Bar dataKey="value" fill="#3b82f6" />
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
                          <Tooltip />
                          <Bar dataKey="tokens" fill="#8b5cf6" />
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
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="duration" fill="#f59e0b" />
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
                        {metrics.agent_stats.map((stat) => (
                          <tr key={stat.agent_name} className="border-b hover:bg-muted/50">
                            <td className="p-2 font-medium">{stat.agent_name}</td>
                            <td className="text-right p-2">{stat.total_requests.toLocaleString()}</td>
                            <td className="text-right p-2 text-green-600">{stat.successful_requests.toLocaleString()}</td>
                            <td className="text-right p-2 text-red-600">{stat.failed_requests.toLocaleString()}</td>
                            <td className="text-right p-2 text-amber-600">{stat.blocked_requests.toLocaleString()}</td>
                            <td className="text-right p-2">{Math.round(stat.avg_duration_ms)}ms</td>
                            <td className="text-right p-2">{stat.total_tokens.toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {metrics.agent_stats.length === 0 && (
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
