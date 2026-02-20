'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Wrench, FileText, Search, Globe } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/lib/i18n';

interface ToolUsageProps {
  tools: Array<{
    name: string;
    query?: string;
    results?: unknown[];
    documentSources?: string[];
  }>;
}

const TOOL_ICONS: Record<string, typeof Wrench> = {
  search: Search,
  web_search: Globe,
  document_search: FileText,
  rag: FileText,
  default: Wrench,
};

export function ToolUsage({ tools }: ToolUsageProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { t } = useTranslation();

  if (!tools || tools.length === 0) return null;

  const totalResults = tools.reduce((acc, tool) => acc + (tool.results?.length || 0), 0);

  const toggleId = `tool-usage-${tools.map(t => t.name).join('-')}`;

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
        aria-label={isExpanded ? 'Hide tool details' : 'Show tool details'}
      >
        <div className="flex items-center gap-2">
          <Wrench className="w-3.5 h-3.5 text-muted-foreground" aria-hidden="true" />
          <span className="font-medium text-muted-foreground">
            {tools.length} {tools.length === 1 ? 'tool' : 'tools'} used
            {totalResults > 0 && ` • ${totalResults} results`}
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
            const resultCount = tool.results?.length || 0;

            return (
              <div
                key={index}
                className="flex items-start gap-2 p-2 rounded bg-muted/50 text-xs"
              >
                <Icon className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0" aria-hidden="true" />
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-medium capitalize">{tool.name}</span>
                    {resultCount > 0 && (
                      <span className="text-muted-foreground">
                        {resultCount} results
                      </span>
                    )}
                  </div>

                  {tool.query && (
                    <div className="text-muted-foreground truncate">
                      Query: {tool.query}
                    </div>
                  )}

                  {tool.documentSources && tool.documentSources.length > 0 && (
                    <div className="space-y-0.5">
                      <span className="text-muted-foreground">Sources:</span>
                      <ul className="list-disc list-inside text-muted-foreground truncate">
                        {tool.documentSources.map((source, idx) => (
                          <li key={idx} className="truncate">{source}</li>
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
