'use client';

import { useState, useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, Loader2, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { MAX_MESSAGE_LENGTH, WARNING_THRESHOLD } from '@/lib/constants';
import { validateMessage, getCharacterCountStatus, type ValidationResult } from '@/lib/security-validator';
import { useTranslation } from '@/lib/i18n';

interface MessageInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function MessageInput({
  onSend,
  disabled,
}: MessageInputProps) {
  const [message, setMessage] = useState('');
  const { t } = useTranslation();

  const validationResult: ValidationResult = useMemo(
    () => validateMessage(message),
    [message]
  );

  const characterCount = message.length;
  const { status, percentage } = getCharacterCountStatus(characterCount);
  const isOverLimit = characterCount > MAX_MESSAGE_LENGTH;
  const isNearLimit = characterCount >= WARNING_THRESHOLD;
  const hasInjectionWarning = !!validationResult.injectionPattern;

  const handleSubmit = useCallback(() => {
    if (validationResult.valid && !disabled) {
      onSend(message.trim());
      setMessage('');
    }
  }, [message, disabled, validationResult.valid, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const getCounterColor = () => {
    if (isOverLimit) return 'text-destructive';
    if (isNearLimit) return 'text-yellow-600 dark:text-yellow-500';
    return 'text-muted-foreground';
  };

  const getProgressColor = () => {
    if (isOverLimit) return 'bg-destructive';
    if (isNearLimit) return 'bg-yellow-600 dark:bg-yellow-500';
    return 'bg-green-600 dark:bg-green-500';
  };

  const getBorderColor = () => {
    if (isOverLimit) return 'border-destructive focus-visible:ring-destructive';
    if (hasInjectionWarning) return 'border-yellow-600 focus-visible:ring-yellow-600';
    return '';
  };

  return (
    <div className="border-t border-border bg-background p-4">
      <div className="flex gap-2 items-end max-w-4xl mx-auto">
        <div className="flex-1 relative">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('chat.inputPlaceholder')}
            disabled={disabled}
            className={cn(
              'min-h-[44px] max-h-[200px] resize-none pr-24 pb-8',
              getBorderColor()
            )}
            rows={1}
            aria-invalid={isOverLimit}
            aria-describedby="character-count warning-message"
          />

          {/* Character Counter Badge */}
          <div className="absolute right-2 bottom-2 flex items-center gap-2">
            {/* Progress Indicator */}
            <div className="flex items-center gap-1.5">
              <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className={cn('h-full transition-all duration-200', getProgressColor())}
                  style={{ width: `${Math.min(percentage, 100)}%` }}
                />
              </div>
              <span
                id="character-count"
                className={cn('text-xs font-medium', getCounterColor())}
              >
                {characterCount.toLocaleString()} / {MAX_MESSAGE_LENGTH.toLocaleString()}
              </span>
            </div>
          </div>

          {/* Injection Pattern Warning */}
          {hasInjectionWarning && !isOverLimit && (
            <div className="absolute top-2 left-2 right-2 flex items-start gap-1.5 p-2 bg-yellow-500/10 border border-yellow-600/30 rounded-md">
              <AlertTriangle className="w-3.5 h-3.5 text-yellow-600 dark:text-yellow-500 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-yellow-700 dark:text-yellow-500">
                {t('chat.injectionWarning', validationResult.injectionPattern)}
              </p>
            </div>
          )}

          {/* Length Error Message */}
          {isOverLimit && (
            <div className="absolute top-2 left-2 right-2 flex items-start gap-1.5 p-2 bg-destructive/10 border border-destructive/30 rounded-md">
              <AlertTriangle className="w-3.5 h-3.5 text-destructive flex-shrink-0 mt-0.5" />
              <p className="text-xs text-destructive font-medium">
                {t('chat.tooLong')}
              </p>
            </div>
          )}
        </div>

        <Button
          onClick={handleSubmit}
          disabled={disabled || !message.trim() || isOverLimit}
          size="icon"
          className="h-11 w-11 flex-shrink-0"
          aria-label="Send message"
        >
          {disabled ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </Button>
      </div>

      {/* Input Hint */}
      <div className="max-w-4xl mx-auto mt-2">
        <p className="text-xs text-muted-foreground text-center">
          {t('chat.inputHint')}
        </p>

        {/* Validation Status Indicators */}
        {(isNearLimit || hasInjectionWarning) && !isOverLimit && (
          <div className="flex items-center justify-center gap-4 mt-2">
            {isNearLimit && (
              <div className="flex items-center gap-1.5 text-xs text-yellow-600 dark:text-yellow-500">
                <div className="w-2 h-2 bg-yellow-600 dark:bg-yellow-500 rounded-full animate-pulse" />
                <span>
                  {Math.ceil(MAX_MESSAGE_LENGTH - characterCount)} {characterCount > 1 ? 'characters' : 'character'} remaining
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
