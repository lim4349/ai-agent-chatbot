import type { ChatRequest, SSECallbacks } from '@/types';
import { API_BASE_URL, API_ENDPOINTS } from './constants';

interface StreamChatOptions {
  maxRetries?: number;
  initialRetryDelay?: number;
  maxRetryDelay?: number;
}

export function streamChat(
  request: ChatRequest,
  callbacks: SSECallbacks,
  options: StreamChatOptions = {}
): { abort: () => void; promise: Promise<void> } {
  const {
    maxRetries = 3,
    initialRetryDelay = 1000,
    maxRetryDelay = 30000,
  } = options;

  const controller = new AbortController();
  let retryCount = 0;
  let retryDelay = initialRetryDelay;

  const promise = (async () => {
    const attemptStream = async (): Promise<void> => {
      try {
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.chatStream}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...request, stream: true }),
          signal: controller.signal,
        });

        if (!response.ok) {
          const error = await response.json().catch(() => ({ error: 'Unknown error' }));
          callbacks.onError(error.error || `HTTP ${response.status}`);
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          callbacks.onError('No response body');
          return;
        }

        const decoder = new TextDecoder();
        let buffer = '';
        let isStreamClosed = false;

        while (!isStreamClosed) {
          try {
            const { done, value } = await reader.read();
            if (done) {
              isStreamClosed = true;
              break;
            }

            buffer += decoder.decode(value, { stream: true });

            // Split by double newlines (handle both \n\n and \r\n\r\n)
            // The \r?\n\r?\n pattern matches both Unix and Windows line endings
            const parts = buffer.split(/\r?\n\r?\n/);
            // Keep the last incomplete part in the buffer
            buffer = parts.pop() || '';

            for (const part of parts) {
              if (!part.trim()) continue;

              const lines = part.split(/\r?\n/);
              let eventType = '';
              let eventData = '';

              for (const line of lines) {
                if (line.startsWith('event:')) {
                  eventType = line.substring(6).trim();
                } else if (line.startsWith('data:')) {
                  // SSE format is "data: value" - the spec says to remove exactly one space after colon
                  // But we need to preserve the actual data content including leading spaces
                  const raw = line.substring(5);
                  // Only remove the single delimiter space, preserve any leading spaces in data
                  eventData = raw.length > 0 && raw[0] === ' ' ? raw.substring(1) : raw;
                }
              }

              if (!eventType) continue;

              switch (eventType) {
                case 'metadata':
                  try {
                    callbacks.onMetadata(JSON.parse(eventData));
                  } catch {
                    // Ignore parse errors
                  }
                  break;
                case 'token':
                  if (eventData) {
                    let isInternalJson = false;
                    if (eventData.startsWith('{') || eventData.startsWith('[')) {
                      try {
                        JSON.parse(eventData);
                        isInternalJson = true;
                      } catch {
                        // Incomplete/non-JSON = normal text token (e.g. markdown link starting with '[')
                      }
                    }
                    if (!isInternalJson) {
                      callbacks.onToken(eventData);
                    }
                  }
                  break;
                case 'agent':
                  try {
                    callbacks.onAgent(JSON.parse(eventData).agent);
                  } catch {
                    // Ignore parse errors
                  }
                  break;
                case 'done':
                  isStreamClosed = true;
                  break;
                case 'error':
                  try {
                    const errorData = JSON.parse(eventData);
                    // Don't retry on client errors (4xx)
                    throw new Error(errorData.error || 'Stream error');
                  } catch {
                    throw new Error(eventData || 'Stream error');
                  }
              }

              if (isStreamClosed) break;
            }
          } catch (readError) {
            // Check if this was an abort
            if (controller.signal.aborted) {
              return;
            }
            throw readError;
          }
        }

        callbacks.onDone();
      } catch (error) {
        // Don't retry if aborted
        if (controller.signal.aborted) {
          return;
        }

        // Don't retry on client errors
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        const isClientError = errorMessage.includes('400') || errorMessage.includes('401') ||
                              errorMessage.includes('403') || errorMessage.includes('404') ||
                              errorMessage.includes('422');

        if (isClientError || retryCount >= maxRetries) {
          callbacks.onError(errorMessage);
          return;
        }

        // Retry with exponential backoff
        retryCount++;
        await new Promise(resolve => setTimeout(resolve, retryDelay));
        retryDelay = Math.min(retryDelay * 2, maxRetryDelay);

        return attemptStream();
      }
    };

    return attemptStream();
  })();

  return {
    abort: () => controller.abort(),
    promise,
  };
}
