interface StreamTokenBufferOptions {
  batchIntervalMs?: number;
  checkIntervalMs?: number;
  maxBufferSize?: number;
}

export class StreamTokenBuffer {
  private buffer = '';
  private interval: ReturnType<typeof setInterval> | null = null;
  private lastFlushTime = Date.now();
  private readonly batchIntervalMs: number;
  private readonly checkIntervalMs: number;
  private readonly maxBufferSize: number;

  constructor(
    private readonly onFlush: (batch: string) => void,
    options: StreamTokenBufferOptions = {}
  ) {
    this.batchIntervalMs = options.batchIntervalMs ?? 100;
    this.checkIntervalMs = options.checkIntervalMs ?? 32;
    this.maxBufferSize = options.maxBufferSize ?? 500;
  }

  push(token: string): void {
    this.buffer += token;
    this.schedule();
  }

  flush(): void {
    if (!this.buffer) return;
    const batch = this.buffer;
    this.buffer = '';
    this.lastFlushTime = Date.now();
    this.onFlush(batch);
  }

  drain(): string {
    const remaining = this.buffer;
    this.buffer = '';
    return remaining;
  }

  clear(): void {
    this.buffer = '';
  }

  stop(): void {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }
  }

  private schedule(): void {
    if (this.interval) return;
    this.interval = setInterval(() => {
      const elapsed = Date.now() - this.lastFlushTime;
      if (this.buffer && (elapsed >= this.batchIntervalMs || this.buffer.length > this.maxBufferSize)) {
        this.flush();
      }
    }, this.checkIntervalMs);
  }
}
