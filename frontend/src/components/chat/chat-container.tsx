'use client';

import { useChatStore, useActiveSession } from '@/stores/chat-store';
import { MessageList } from './message-list';
import { ChatInput } from './chat-input';

export function ChatContainer() {
  const isStreaming = useChatStore((state) => state.isStreaming);
  const sendMessage = useChatStore((state) => state.sendMessage);
  const activeSession = useActiveSession();

  const messages = activeSession?.messages || [];

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
      <MessageList messages={messages} isStreaming={isStreaming} />
      <ChatInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  );
}
