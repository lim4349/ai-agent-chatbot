import { describe, expect, it } from 'vitest';
import { classifyChatError } from './chat-errors';

describe('classifyChatError', () => {
  it('classifies network errors', () => {
    expect(classifyChatError('fetch failed').type).toBe('network');
  });

  it('classifies timeout errors', () => {
    expect(classifyChatError('request timed out').type).toBe('timeout');
  });

  it('classifies retryable server errors', () => {
    expect(classifyChatError('HTTP 503').type).toBe('server');
  });

  it('falls back to unknown errors', () => {
    const error = classifyChatError('unexpected');

    expect(error.type).toBe('unknown');
    expect(error.retryable).toBe(true);
  });
});
