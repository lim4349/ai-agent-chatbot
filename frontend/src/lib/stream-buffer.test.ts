import { afterEach, describe, expect, it, vi } from 'vitest';
import { StreamTokenBuffer } from './stream-buffer';

describe('StreamTokenBuffer', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('flushes buffered tokens after the batch interval', () => {
    vi.useFakeTimers();
    const flushed: string[] = [];
    const buffer = new StreamTokenBuffer((batch) => flushed.push(batch), {
      batchIntervalMs: 100,
      checkIntervalMs: 10,
    });

    buffer.push('안녕');
    vi.advanceTimersByTime(99);
    expect(flushed).toEqual([]);

    vi.advanceTimersByTime(10);
    expect(flushed).toEqual(['안녕']);
    buffer.stop();
  });

  it('drains remaining tokens without invoking the flush callback', () => {
    vi.useFakeTimers();
    const flushed: string[] = [];
    const buffer = new StreamTokenBuffer((batch) => flushed.push(batch));

    buffer.push('final');
    expect(buffer.drain()).toBe('final');
    expect(flushed).toEqual([]);
    buffer.stop();
  });
});
