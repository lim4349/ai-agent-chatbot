'use client';

import { useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp, Wrench, FileText, Search, Globe } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation, type TranslationKey } from '@/lib/i18n';
import type { EvidenceItem } from '@/types';

interface ToolUsageProps {
  tools: Array<{
    name: string;
    query?: string;
    results?: unknown[] | string;
    documentSources?: string[];
    sources?: string[];
    confidence?: string;
    evidenceItems?: EvidenceItem[];
    status?: string;
  }>;
}

const TOOL_ICONS: Record<string, typeof Wrench> = {
  search: Search,
  web_search: Globe,
  document_search: FileText,
  retriever: FileText,
  default: Wrench,
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

export function ToolUsage({ tools }: ToolUsageProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { t } = useTranslation();

  if (!tools || tools.length === 0) return null;

  const totalResults = tools.reduce((acc, tool) => {
    if (tool.evidenceItems?.length) return acc + tool.evidenceItems.length;
    if (Array.isArray(tool.results)) return acc + tool.results.length;
    if (typeof tool.results === 'string' && tool.results.trim()) return acc + 1;
    return acc;
  }, 0);

  const toggleId = `tool-usage-${tools.map((tool) => tool.name).join('-')}`;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setIsExpanded(!isExpanded);
    }
  };

  return (
    <div className="mt-2 rounded-md border border-border/50 bg-muted/30 overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        onKeyDown={handleKeyDown}
        className="w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-muted/50 transition-colors"
        aria-expanded={isExpanded}
        aria-controls={toggleId}
        aria-label={isExpanded ? t('tool.hideDetails') : t('tool.showDetails')}
      >
        <div className="flex items-center gap-2">
          <Wrench className="w-3.5 h-3.5 text-muted-foreground" aria-hidden="true" />
          <span className="font-medium text-muted-foreground">
            {t('tool.used', tools.length)}
            {totalResults > 0 && ` • ${t('tool.results', totalResults)}`}
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" aria-hidden="true" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" aria-hidden="true" />
        )}
      </button>

      <div
        id={toggleId}
        className={cn(
          'overflow-hidden transition-all duration-200',
          isExpanded ? 'max-h-[720px] opacity-100' : 'max-h-0 opacity-0'
        )}
      >
        <div className="px-3 pb-3 space-y-2">
          {tools.map((tool, index) => {
            const Icon = TOOL_ICONS[tool.name] || TOOL_ICONS.default;
            const resultCount = Array.isArray(tool.results)
              ? tool.results.length
              : typeof tool.results === 'string' && tool.results.trim()
                ? 1
                : 0;
            const sources = tool.sources || tool.documentSources || [];
            const evidenceItems = tool.evidenceItems || [];
            const toolLabelKey = TOOL_LABEL_KEYS[tool.name];
            const confidenceLabelKey = tool.confidence ? CONFIDENCE_LABEL_KEYS[tool.confidence] : undefined;

            return (
              <div
                key={index}
                className="flex items-start gap-2 p-2 rounded bg-muted/50 text-xs"
              >
                <Icon className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0" aria-hidden="true" />
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">
                      {toolLabelKey ? t(toolLabelKey) : tool.name || t('tool.unknown')}
                    </span>
                    {resultCount > 0 && (
                      <span className="text-muted-foreground">
                        {t('tool.results', resultCount)}
                      </span>
                    )}
                    {tool.status === 'error' && (
                      <span className="text-destructive">{t('tool.error')}</span>
                    )}
                  </div>

                  {tool.confidence && (
                    <div className="text-muted-foreground">
                      {t('tool.confidence')}: {' '}
                      <span className="font-medium">
                        {confidenceLabelKey ? t(confidenceLabelKey) : tool.confidence}
                      </span>
                    </div>
                  )}

                  {sources.length > 0 && (
                    <div className="space-y-0.5">
                      <span className="text-muted-foreground">{t('tool.sources')}:</span>
                      <ul className="list-disc list-inside text-muted-foreground">
                        {sources.map((source, idx) => (
                          <li key={idx} className="break-all">{source}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {evidenceItems.length > 0 && (
                    <div className="space-y-1.5 pt-1">
                      <span className="text-muted-foreground">{t('tool.evidence')}:</span>
                      <div className="space-y-1.5">
                        {evidenceItems.map((item, idx) => {
                          const itemConfidenceKey = item.confidence
                            ? CONFIDENCE_LABEL_KEYS[item.confidence]
                            : undefined;
                          const isWeak = item.confidence === 'low' || item.confidence === 'none';
                          const pageLabel = formatPageLabel(item.page, item.page_end, t);
                          const scoreLabel =
                            typeof item.score === 'number' ? item.score.toFixed(2) : undefined;

                          return (
                            <div
                              key={`${item.source}-${idx}`}
                              className={cn(
                                'rounded border bg-background/70 p-2 space-y-1',
                                isWeak ? 'border-amber-500/50' : 'border-border/60'
                              )}
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <div className="break-words font-medium text-foreground">
                                    {item.title || item.source || t('tool.unknownSource')}
                                  </div>
                                  {pageLabel && (
                                    <div className="text-muted-foreground">{pageLabel}</div>
                                  )}
                                </div>
                                {isWeak && (
                                  <AlertTriangle
                                    className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-amber-500"
                                    aria-label={t('tool.lowConfidence')}
                                  />
                                )}
                              </div>

                              {item.heading_path && (
                                <div className="break-words text-muted-foreground">
                                  {t('tool.heading')}: {item.heading_path}
                                </div>
                              )}

                              <div className="flex flex-wrap gap-x-3 gap-y-1 text-muted-foreground">
                                {item.confidence && (
                                  <span>
                                    {t('tool.confidence')}: {' '}
                                    {itemConfidenceKey ? t(itemConfidenceKey) : item.confidence}
                                  </span>
                                )}
                                {scoreLabel && <span>{t('tool.score')}: {scoreLabel}</span>}
                              </div>

                              {item.snippet && (
                                <blockquote className="max-h-28 overflow-y-auto whitespace-pre-wrap break-words border-l-2 border-border pl-2 text-muted-foreground">
                                  {item.snippet}
                                </blockquote>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function formatPageLabel(
  page: number | null | undefined,
  pageEnd: number | null | undefined,
  t: ReturnType<typeof useTranslation>['t']
): string {
  if (!page) return '';
  if (pageEnd && pageEnd !== page) {
    return t('tool.pages', page, pageEnd);
  }
  return t('tool.page', page);
}
