'use client';

import { useState, useCallback, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, Loader2, ShieldAlert, XCircle, AlertTriangle, Info, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { MAX_MESSAGE_LENGTH, WARNING_THRESHOLD } from '@/lib/constants';
import {
  validateSecurity,
  sanitizeInput,
  shouldBlockMessage,
  getSeverityClass,
  type ValidationResult,
  type SecurityConfig,
} from '@/lib/security-validator';
import { useTranslation } from '@/lib/i18n';

// Security configuration - moved outside component to prevent re-renders
const SECURITY_CONFIG: SecurityConfig = {
  maxMessageLength: MAX_MESSAGE_LENGTH,
  enableRealTimeValidation: true,
  showInjectionWarnings: true,
};

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [showWarning, setShowWarning] = useState(true);
  const { t, locale } = useTranslation();

  // Real-time validation with useMemo to avoid setState in effect
  const newValidation = useMemo(() => {
    if (message.length > 0 && SECURITY_CONFIG.enableRealTimeValidation) {
      return validateSecurity(message, SECURITY_CONFIG, locale);
    }
    return null;
  }, [message, locale]);

  // Sync validation state
  useEffect(() => {
    setValidation(newValidation);
  }, [newValidation]);

  const handleSubmit = useCallback(() => {
    const trimmed = message.trim();

    // Check if message should be blocked
    if (validation && shouldBlockMessage(validation.severity)) {
      return; // Block submission for critical/error severity
    }

    if (trimmed && !disabled) {
      onSend(trimmed);
      setMessage('');
      setValidation(null);
      setShowWarning(true);
    }
  }, [message, disabled, onSend, validation]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const rawValue = e.target.value;
    const sanitized = sanitizeInput(rawValue);
    setMessage(sanitized);
  };

  const dismissWarning = () => {
    setShowWarning(false);
  };

  const characterCount = message.length;
  const isOverLimit = characterCount > MAX_MESSAGE_LENGTH;
  const isNearLimit = characterCount >= WARNING_THRESHOLD && characterCount <= MAX_MESSAGE_LENGTH;

  // Determine if send button should be disabled
  const shouldDisableSend: boolean =
    !!disabled ||
    !message.trim() ||
    isOverLimit ||
    (validation !== null && shouldBlockMessage(validation.severity));

  return (
    <div className="border-t border-border bg-background p-4">
      <div className="flex gap-2 items-end max-w-4xl mx-auto">
        <div className="flex-1 relative">
          <Textarea
            value={message}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={t('chat.inputPlaceholder')}
            disabled={disabled}
            className={cn(
              'min-h-[44px] max-h-[200px] resize-none pr-16',
              isOverLimit && 'border-destructive focus-visible:ring-destructive',
              validation?.severity === 'critical' && 'border-red-500 focus-visible:ring-red-500',
              validation?.severity === 'error' && 'border-red-500 focus-visible:ring-red-500',
              validation?.severity === 'warning' && 'border-yellow-500 focus-visible:ring-yellow-500'
            )}
            rows={1}
          />
          <span
            className={cn(
              'absolute right-2 bottom-2 text-xs',
              isOverLimit ? 'text-destructive' : isNearLimit ? 'text-yellow-600 dark:text-yellow-400' : 'text-muted-foreground'
            )}
          >
            {characterCount}/{MAX_MESSAGE_LENGTH}
          </span>
        </div>
        <Button
          onClick={handleSubmit}
          disabled={shouldDisableSend}
          size="icon"
          className={cn(
            'h-11 w-11',
            validation?.severity === 'critical' && 'bg-red-600 hover:bg-red-700'
          )}
          title={validation?.message || undefined}
        >
          {disabled ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </Button>
      </div>

      {/* Security Warning Banner */}
      {validation && showWarning && validation.message && (
        <div className={cn(
          'mt-2 p-3 rounded-lg border flex items-start gap-2 animate-in slide-in-from-top-2',
          getSeverityClass(validation.severity)
        )}>
          {validation.severity === 'critical' && (
            <ShieldAlert className="w-4 h-4 mt-0.5 flex-shrink-0" />
          )}
          {validation.severity === 'error' && (
            <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          )}
          {validation.severity === 'warning' && (
            <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          )}
          {validation.severity === 'info' && (
            <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
          )}
          <div className="flex-1">
            <span className="text-sm">{validation.message}</span>
            {validation.patterns && validation.patterns.length > 0 && (
              <div className="text-xs mt-1 opacity-80">
                {locale === 'ko' ? '감지된 패턴: ' : 'Patterns detected: '}
                {validation.patterns.join(', ')}
              </div>
            )}
          </div>
          {validation.severity !== 'critical' && validation.severity !== 'error' && (
            <button
              onClick={dismissWarning}
              className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
              aria-label={locale === 'ko' ? '닫기' : 'Dismiss'}
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      )}

      {/* Input hint */}
      <p className="text-xs text-muted-foreground text-center mt-2">
        {t('chat.inputHint')}
      </p>
    </div>
  );
}
