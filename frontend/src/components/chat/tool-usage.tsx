'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Wrench, FileText, Search, Globe } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation, type TranslationKey } from '@/lib/i18n';

interface ToolUsageProps {
  tools: Array<{
    name: string;
    query?: string;
    results?: unknown[] | string;
    documentSources?: string[];
    sources?: string[];
    confidence?: string;
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
          isExpanded ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'
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
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
