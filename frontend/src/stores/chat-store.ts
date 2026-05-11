import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { v4 as uuidv4 } from 'uuid';
import type { Session, HealthResponse } from '@/types';
import { streamChat } from '@/lib/sse';
import { api } from '@/lib/api';
import { parseMemoryCommand, type ParsedMemoryCommand } from '@/lib/memory-commands';
import {
  addTurnToSession,
  appendAssistantContent,
  appendToolToLastAssistant,
  createChatTurn,
  removeEmptyAssistantTail,
  removeLastTurn,
  setLastAssistantAgent,
  setLastAssistantAgents,
  setLastAssistantContent,
  setLastAssistantStatus,
} from './chat-turn';
import { useToastStore } from './toast-store';

// Device ID for guest mode (no login required)
const DEVICE_ID_KEY = 'device_id';

// Error classification utility
function classifyError(error: string): ChatError {
  const lowerError = error.toLowerCase();

  // Network errors
  if (lowerError.includes('network') || lowerError.includes('fetch') ||
      lowerError.includes('connection') || lowerError.includes('econnrefused') ||
      lowerError.includes('name or service not known') || lowerError.includes('dns')) {
    return {
      message: '네트워크 연결이 불안정합니다. 인터넷 연결을 확인해주세요.',
      type: 'network',
      retryable: true,
      originalError: error,
    };
  }

  // Timeout errors
  if (lowerError.includes('timeout') || lowerError.includes('timed out')) {
    return {
      message: '요청 시간이 초과되었습니다. 다시 시도해주세요.',
      type: 'timeout',
      retryable: true,
      originalError: error,
    };
  }

  // Server errors
  if (lowerError.includes('500') || lowerError.includes('502') ||
      lowerError.includes('503') || lowerError.includes('429') ||
      lowerError.includes('server error')) {
    return {
      message: '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
      type: 'server',
      retryable: true,
      originalError: error,
    };
  }

  // Unknown errors
  return {
    message: '오류가 발생했습니다. 다시 시도해주세요.',
    type: 'unknown',
    retryable: true,
    originalError: error,
  };
}

export function getDeviceId(): string {
  if (typeof window === 'undefined') return '';
  let deviceId = localStorage.getItem(DEVICE_ID_KEY);
  if (!deviceId) {
    deviceId = `device_${uuidv4()}`;
    localStorage.setItem(DEVICE_ID_KEY, deviceId);
  }
  return deviceId;
}

// Error types for better error handling
export type ErrorType = 'network' | 'timeout' | 'server' | 'unknown';

export interface ChatError {
  message: string;
  type: ErrorType;
  retryable: boolean;
  originalError?: string;
}

interface ChatStore {
  sessions: Session[];
  activeSessionId: string | null;
  isStreaming: boolean;
  error: ChatError | null;
  health: HealthResponse | null;
  sidebarOpen: boolean;
  _hasHydrated: boolean;

  setHasHydrated: (state: boolean) => void;
  createSession: () => Promise<string>;
  switchSession: (id: string) => void;
  deleteSession: (id: string) => Promise<void>;
  sendMessage: (content: string) => void;
  setStreaming: (value: boolean) => void;
  setError: (error: ChatError | null) => void;
  setHealth: (health: HealthResponse | null) => void;
  toggleSidebar: () => void;
  clearCurrentSession: () => Promise<string | undefined>;
  cancelStreaming: () => void;
  retryLastMessage: () => void;

  // Memory command handling
  lastMemoryCommand: ParsedMemoryCommand | null;
  showMemoryFeedback: boolean;
  showMemoryModal: boolean;
  memories: string[];
  showCommandFeedback: (command: ParsedMemoryCommand) => void;
  dismissMemoryFeedback: () => void;
  setShowMemoryModal: (show: boolean) => void;
  addMemory: (content: string) => void;
  removeMemory: (index: number) => void;
  clearMemories: () => void;

  // Internal state for retry functionality
  _lastMessageContent: string;
  _currentStreamAbort: (() => void) | null;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      sessions: [],
      activeSessionId: null,
      isStreaming: false,
      error: null,
      health: null,
      sidebarOpen: true,
      _hasHydrated: false,

      // Memory command state
      lastMemoryCommand: null,
      showMemoryFeedback: false,
      showMemoryModal: false,
      memories: [],

      // Internal state for retry functionality
      _lastMessageContent: '',
      _currentStreamAbort: null,

      setHasHydrated: (state) => set({ _hasHydrated: state }),

      createSession: async () => {
        // Create session locally only - will be synced to backend on first message
        const id = uuidv4();
        const now = new Date();
        const newSession: Session = {
          id,
          title: 'New Chat',
          messages: [],
          createdAt: now,
          isLocalOnly: true, // Mark as local-only until first message
        };
        set((state) => ({
          sessions: [newSession, ...state.sessions],
          activeSessionId: id,
        }));
        return id;
      },

      switchSession: (id) => {
        set({ activeSessionId: id });
      },

      deleteSession: async (id) => {
        try {
          // Call backend API to delete session from Supabase and Pinecone
          const deviceId = getDeviceId();
          await api.deleteSession(id, deviceId);
        } catch (error) {
          console.error('Failed to delete session from backend:', error);
          const { addToast } = useToastStore.getState();
          addToast('Failed to delete session from server', 'error');
        }
        // Always update local state
        set((state) => {
          const sessions = state.sessions.filter((s) => s.id !== id);
          const activeSessionId =
            state.activeSessionId === id
              ? sessions[0]?.id || null
              : state.activeSessionId;
          return { sessions, activeSessionId };
        });
      },

      sendMessage: (content) => {
        const { activeSessionId, isStreaming, showCommandFeedback, sessions } = get();
        if (isStreaming || !activeSessionId) return;

        // Store message content for retry functionality
        set({ _lastMessageContent: content });

        // Parse memory commands for instant feedback
        const command = parseMemoryCommand(content);
        if (command.type !== 'none') {
          showCommandFeedback(command);
        }

        const sessionId = activeSessionId;
        const currentSession = sessions.find((s) => s.id === sessionId);

        // Sync local-only session to backend on first message
        if (currentSession?.isLocalOnly) {
          const deviceId = getDeviceId();
          api
            .createSession(currentSession.title || 'New Chat', deviceId, sessionId)
            .then(() => {
              // Mark as synced
              set((state) => ({
                sessions: state.sessions.map((s) =>
                  s.id === sessionId ? { ...s, isLocalOnly: false } : s
                ),
              }));
            })
            .catch((error) => {
              console.error('Failed to sync session to backend:', error);
              // Continue anyway - session works locally
            });
        }
        const { userMessage, assistantMessage } = createChatTurn(content);

        set((state) => ({
          sessions: addTurnToSession(
            state.sessions,
            sessionId,
            content,
            userMessage,
            assistantMessage
          ),
          isStreaming: true,
          error: null,
        }));

        // Token batching for smooth streaming - batch by time instead of rAF
        let tokenBuffer = '';
        let flushInterval: NodeJS.Timeout | null = null;
        let lastFlushTime = Date.now();

        // Constants for performance optimization
        const BATCH_INTERVAL = 100; // Increased from 50ms to 100ms
        const CHECK_INTERVAL = 32; // ~30fps instead of 60fps
        const MAX_BUFFER_SIZE = 500; // Max characters to buffer before forced flush
        const flushTokens = () => {
          if (!tokenBuffer) return;
          const batch = tokenBuffer;
          tokenBuffer = '';
          lastFlushTime = Date.now();
          set((state) => ({
            sessions: appendAssistantContent(state.sessions, sessionId, batch),
          }));
        };

        // Flush every BATCH_INTERVAL (100ms) for smoother rendering, or when buffer gets large
        const scheduleFlush = () => {
          if (flushInterval) return;
          flushInterval = setInterval(() => {
            const now = Date.now();
            const timeSinceLastFlush = now - lastFlushTime;
            // Flush if: buffer has content AND (BATCH_INTERVAL passed OR buffer > MAX_BUFFER_SIZE)
            if (tokenBuffer && (timeSinceLastFlush >= BATCH_INTERVAL || tokenBuffer.length > MAX_BUFFER_SIZE)) {
              flushTokens();
            }
          }, CHECK_INTERVAL); // ~30fps check
        };

        const streamRequest = streamChat(
          { message: content, session_id: sessionId, device_id: getDeviceId() },
          {
            onMetadata: () => {},
            onToken: (token) => {
              tokenBuffer += token;
              scheduleFlush();
            },
            onAgent: (agent, allAgents) => {
              set((state) => ({
                sessions: setLastAssistantAgent(state.sessions, sessionId, agent, allAgents),
              }));
            },
            onStatus: (status) => {
              set((state) => ({
                sessions: setLastAssistantStatus(state.sessions, sessionId, status),
              }));
            },
            onTool: (tool) => {
              const toolName = tool.tool || tool.name || 'tool';
              set((state) => ({
                sessions: appendToolToLastAssistant(state.sessions, sessionId, {
                  name: toolName,
                  query: tool.query,
                  results: tool.results,
                  status: tool.error ? 'error' : 'success',
                }),
              }));
            },
            onAgentsComplete: (agents) => {
              // Final update with all agents that participated
              set((state) => ({
                sessions: setLastAssistantAgents(state.sessions, sessionId, agents),
              }));
            },
            onDone: () => {
              // Flush any remaining tokens
              if (flushInterval) {
                clearInterval(flushInterval);
                flushInterval = null;
              }
              if (tokenBuffer) {
                const remaining = tokenBuffer;
                tokenBuffer = '';
                set((state) => ({
                  sessions: appendAssistantContent(state.sessions, sessionId, remaining),
                  isStreaming: false,
                  _currentStreamAbort: null,
                }));
              } else {
                set({ isStreaming: false, _currentStreamAbort: null });
              }
            },
            onError: (error) => {
              if (flushInterval) {
                clearInterval(flushInterval);
                flushInterval = null;
              }
              tokenBuffer = '';
              const classifiedError = classifyError(error);
              set((state) => ({
                isStreaming: false,
                _currentStreamAbort: null,
                error: classifiedError,
                sessions: setLastAssistantContent(state.sessions, sessionId, classifiedError.message),
              }));
            },
          }
        );
        set({ _currentStreamAbort: streamRequest.abort });
      },

      setStreaming: (value) => set({ isStreaming: value }),
      setError: (error) => set({ error }),
      setHealth: (health) => set({ health }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

      retryLastMessage: () => {
        const { _lastMessageContent, activeSessionId, sessions } = get();
        if (!_lastMessageContent || !activeSessionId) return;

        // Remove the last user and assistant messages
        const currentSession = sessions.find((s) => s.id === activeSessionId);
        if (!currentSession || currentSession.messages.length < 2) return;

        // Remove the last assistant and user messages
        set((state) => ({
          sessions: removeLastTurn(state.sessions, activeSessionId),
          error: null,
        }));

        // Resend the message
        setTimeout(() => {
          get().sendMessage(_lastMessageContent);
        }, 100);
      },

      clearCurrentSession: async () => {
        const { activeSessionId, sessions } = get();
        if (!activeSessionId) return;

        get().cancelStreaming();
        const currentSession = sessions.find((session) => session.id === activeSessionId);
        if (!currentSession || currentSession.messages.length === 0) {
          return activeSessionId;
        }

        const nextSessionId = await get().createSession();
        const { addToast } = useToastStore.getState();
        addToast('새 대화를 시작했어요.', 'info');
        return nextSessionId;
      },

      cancelStreaming: () => {
        const { activeSessionId, _currentStreamAbort } = get();
        _currentStreamAbort?.();

        if (!activeSessionId) {
          set({ isStreaming: false, _currentStreamAbort: null });
          return;
        }

        set((state) => ({
          isStreaming: false,
          _currentStreamAbort: null,
          sessions: removeEmptyAssistantTail(state.sessions, activeSessionId),
        }));
      },

      // Memory command actions
      showCommandFeedback: (command) => {
        if (command.type === 'none') return;

        set({
          lastMemoryCommand: command,
          showMemoryFeedback: true,
        });

        // Show toast notification
        const { addToast } = useToastStore.getState();
        switch (command.type) {
          case 'remember':
            addToast('정보를 저장했습니다', 'success');
            if (command.content) {
              get().addMemory(command.content);
            }
            break;
          case 'recall':
            addToast('저장된 정보를 불러옵니다', 'info');
            set({ showMemoryModal: true });
            break;
          case 'forget':
            addToast('정보를 삭제했습니다', 'warning');
            break;
          case 'summarize':
            addToast('대화를 요약했습니다', 'success');
            break;
        }

        // Auto-dismiss feedback after 3 seconds
        setTimeout(() => {
          set({ showMemoryFeedback: false });
        }, 3000);
      },

      dismissMemoryFeedback: () =>
        set({ showMemoryFeedback: false, lastMemoryCommand: null }),

      setShowMemoryModal: (show) =>
        set({ showMemoryModal: show }),

      addMemory: (content) =>
        set((state) => ({
          memories: [...state.memories, content],
        })),

      removeMemory: (index) =>
        set((state) => ({
          memories: state.memories.filter((_, i) => i !== index),
        })),

      clearMemories: () =>
        set({ memories: [] }),
    }),
    {
      name: 'chat-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sessions: state.sessions,
        activeSessionId: state.activeSessionId,
        memories: state.memories,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);

export const useActiveSession = () => {
  const sessions = useChatStore((state) => state.sessions);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  return sessions.find((s) => s.id === activeSessionId);
};
