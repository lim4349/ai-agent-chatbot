import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { v4 as uuidv4 } from 'uuid';
import type { Session, Message, HealthResponse } from '@/types';
import { streamChat } from '@/lib/sse';
import { api } from '@/lib/api';
import { parseMemoryCommand, type ParsedMemoryCommand } from '@/lib/memory-commands';
import { useToastStore } from './toast-store';

// Device ID for guest mode (no login required)
const DEVICE_ID_KEY = 'device_id';

export function getDeviceId(): string {
  if (typeof window === 'undefined') return '';
  let deviceId = localStorage.getItem(DEVICE_ID_KEY);
  if (!deviceId) {
    deviceId = `device_${uuidv4()}`;
    localStorage.setItem(DEVICE_ID_KEY, deviceId);
  }
  return deviceId;
}

interface ChatStore {
  sessions: Session[];
  activeSessionId: string | null;
  isStreaming: boolean;
  error: string | null;
  health: HealthResponse | null;
  sidebarOpen: boolean;
  _hasHydrated: boolean;

  setHasHydrated: (state: boolean) => void;
  createSession: () => Promise<string>;
  switchSession: (id: string) => void;
  deleteSession: (id: string) => Promise<void>;
  sendMessage: (content: string) => void;
  setStreaming: (value: boolean) => void;
  setError: (error: string | null) => void;
  setHealth: (health: HealthResponse | null) => void;
  toggleSidebar: () => void;
  clearCurrentSession: () => void;

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

      setHasHydrated: (state) => set({ _hasHydrated: state }),

      createSession: async () => {
        try {
          // Call backend API to create session in Supabase with device_id
          const deviceId = getDeviceId();
          const response = await api.createSession('New Chat', deviceId);
          const id = response.id;
          const newSession: Session = {
            id,
            title: response.title,
            messages: [],
            createdAt: new Date(response.created_at),
          };
          set((state) => ({
            sessions: [newSession, ...state.sessions],
            activeSessionId: id,
          }));
          return id;
        } catch (error) {
          console.error('Failed to create session in backend, using local fallback:', error);
          // Fallback to local creation if API fails
          const id = uuidv4();
          const now = new Date().toISOString();
          const newSession: Session = {
            id,
            title: 'New Chat',
            messages: [],
            createdAt: now as unknown as Date,
          };
          set((state) => ({
            sessions: [newSession, ...state.sessions],
            activeSessionId: id,
          }));
          return id;
        }
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
        const { activeSessionId, isStreaming, showCommandFeedback } = get();
        if (isStreaming || !activeSessionId) return;

        // Parse memory commands for instant feedback
        const command = parseMemoryCommand(content);
        if (command.type !== 'none') {
          showCommandFeedback(command);
        }

        const sessionId = activeSessionId;
        const now = new Date().toISOString();
        const userMessage: Message = {
          id: uuidv4(),
          role: 'user',
          content,
          createdAt: now as unknown as Date,
        };

        const assistantMessage: Message = {
          id: uuidv4(),
          role: 'assistant',
          content: '',
          createdAt: now as unknown as Date,
        };

        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId
              ? {
                  ...s,
                  title: s.messages.length === 0 ? content.slice(0, 40) : s.title,
                  messages: [...s.messages, userMessage, assistantMessage],
                }
              : s
          ),
          isStreaming: true,
          error: null,
        }));

        // Token batching for smooth streaming - batch by time instead of rAF
        let tokenBuffer = '';
        let flushInterval: NodeJS.Timeout | null = null;
        let lastFlushTime = Date.now();

        const flushTokens = () => {
          if (!tokenBuffer) return;
          const batch = tokenBuffer;
          tokenBuffer = '';
          lastFlushTime = Date.now();
          set((state) => ({
            sessions: state.sessions.map((s) =>
              s.id === sessionId
                ? {
                    ...s,
                    messages: s.messages.map((m, idx) =>
                      idx === s.messages.length - 1
                        ? { ...m, content: m.content + batch }
                        : m
                    ),
                  }
                : s
            ),
          }));
        };

        // Flush every 50ms for smoother rendering, or when buffer gets large
        const scheduleFlush = () => {
          if (flushInterval) return;
          flushInterval = setInterval(() => {
            const now = Date.now();
            const timeSinceLastFlush = now - lastFlushTime;
            // Flush if: buffer has content AND (50ms passed OR buffer > 100 chars)
            if (tokenBuffer && (timeSinceLastFlush >= 50 || tokenBuffer.length > 100)) {
              flushTokens();
            }
          }, 16); // ~60fps check
        };

        streamChat(
          { message: content, session_id: sessionId },
          {
            onMetadata: () => {},
            onToken: (token) => {
              tokenBuffer += token;
              scheduleFlush();
            },
            onAgent: (agent) => {
              set((state) => ({
                sessions: state.sessions.map((s) =>
                  s.id === sessionId
                    ? {
                        ...s,
                        messages: s.messages.map((m, idx) =>
                          idx === s.messages.length - 1 ? { ...m, agent } : m
                        ),
                      }
                    : s
                ),
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
                  sessions: state.sessions.map((s) =>
                    s.id === sessionId
                      ? {
                          ...s,
                          messages: s.messages.map((m, idx) =>
                            idx === s.messages.length - 1
                              ? { ...m, content: m.content + remaining }
                              : m
                          ),
                        }
                      : s
                  ),
                  isStreaming: false,
                }));
              } else {
                set({ isStreaming: false });
              }
            },
            onError: (error) => {
              if (flushInterval) {
                clearInterval(flushInterval);
                flushInterval = null;
              }
              tokenBuffer = '';
              set((state) => ({
                isStreaming: false,
                error,
                sessions: state.sessions.map((s) =>
                  s.id === sessionId
                    ? {
                        ...s,
                        messages: s.messages.map((m, idx) =>
                          idx === s.messages.length - 1
                            ? { ...m, content: `Error: ${error}` }
                            : m
                        ),
                      }
                    : s
                ),
              }));
            },
          }
        );
      },

      setStreaming: (value) => set({ isStreaming: value }),
      setError: (error) => set({ error }),
      setHealth: (health) => set({ health }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

      clearCurrentSession: async () => {
        const { activeSessionId } = get();
        if (!activeSessionId) return;

        try {
          await api.clearSession(activeSessionId);
          set((state) => ({
            sessions: state.sessions.map((s) =>
              s.id === activeSessionId ? { ...s, messages: [] } : s
            ),
          }));
        } catch (error) {
          console.error('Failed to clear session:', error);
        }
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
