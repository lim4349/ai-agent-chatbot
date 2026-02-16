import type { ChatRequest, SSECallbacks } from '@/types';
import { API_BASE_URL, API_ENDPOINTS } from './constants';

/**
 * Fix spacing issues in streaming text
 * Some LLMs (like GLM) may generate tokens without proper spacing after sentence endings
 */
function fixTokenSpacing(text: string): string {
  // Add space after sentence-ending punctuation if followed by a letter
  // Matches: period, exclamation, question mark (Korean/English) followed by a letter without space
  return text.replace(/([.!?。！？])([A-Za-z가-힣])/g, '$1 $2');
}

export function streamChat(
  request: ChatRequest,
  callbacks: SSECallbacks
): { abort: () => void; promise: Promise<void> } {
  const controller = new AbortController();

  const promise = (async () => {
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

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

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
              // Filter out internal LangGraph JSON data
              if (eventData && !eventData.startsWith('[') && !eventData.startsWith('{')) {
                callbacks.onToken(eventData);
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
              callbacks.onDone();
              break;
            case 'error':
              try {
                callbacks.onError(JSON.parse(eventData).error);
              } catch {
                callbacks.onError(eventData);
              }
              break;
          }
        }
      }

      callbacks.onDone();
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }
      callbacks.onError(error instanceof Error ? error.message : 'Unknown error');
    }
  })();

  return {
    abort: () => controller.abort(),
    promise,
  };
}
