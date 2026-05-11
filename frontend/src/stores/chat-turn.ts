import { v4 as uuidv4 } from 'uuid';
import type { Message, Session } from '@/types';

export const MAX_STREAMING_MESSAGE_SIZE = 10000;

export function generateChatTitle(text: string): string {
  const withoutCodeBlocks = text.replace(/```[\s\S]*?```/g, ' ');
  const withoutInlineCode = withoutCodeBlocks.replace(/`[^`]+`/g, ' ');
  const withoutMarkdown = withoutInlineCode
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/[#*_~]/g, '');
  const cleaned = withoutMarkdown.replace(/\s+/g, ' ').trim();
  if (cleaned.length <= 40) return cleaned;
  const truncated = cleaned.slice(0, 40);
  const lastSpace = truncated.lastIndexOf(' ');
  return (lastSpace > 20 ? truncated.slice(0, lastSpace) : truncated) + '...';
}

export function createChatTurn(content: string): { userMessage: Message; assistantMessage: Message } {
  const now = new Date().toISOString();
  return {
    userMessage: {
      id: uuidv4(),
      role: 'user',
      content,
      createdAt: now as unknown as Date,
    },
    assistantMessage: {
      id: uuidv4(),
      role: 'assistant',
      content: '',
      createdAt: now as unknown as Date,
    },
  };
}

export function addTurnToSession(
  sessions: Session[],
  sessionId: string,
  content: string,
  userMessage: Message,
  assistantMessage: Message
): Session[] {
  return sessions.map((session) =>
    session.id === sessionId
      ? {
          ...session,
          title: session.messages.length === 0 ? generateChatTitle(content) : session.title,
          messages: [...session.messages, userMessage, assistantMessage],
        }
      : session
  );
}

export function updateLastAssistantMessage(
  sessions: Session[],
  sessionId: string,
  update: (message: Message) => Message
): Session[] {
  return sessions.map((session) => {
    if (session.id !== sessionId) return session;

    const lastIndex = session.messages.length - 1;
    const lastMessage = session.messages[lastIndex];
    if (!lastMessage || lastMessage.role !== 'assistant') return session;

    const nextMessage = update(lastMessage);
    if (nextMessage === lastMessage) return session;

    const messages = [...session.messages];
    messages[lastIndex] = nextMessage;
    return { ...session, messages };
  });
}

export function appendAssistantContent(
  sessions: Session[],
  sessionId: string,
  content: string,
  maxMessageSize = MAX_STREAMING_MESSAGE_SIZE
): Session[] {
  return updateLastAssistantMessage(sessions, sessionId, (message) => {
    const newContent = message.content + content;
    const trimmedContent =
      newContent.length > maxMessageSize
        ? newContent.slice(0, maxMessageSize) + '\n\n[Message truncated due to length]'
        : newContent;
    return { ...message, content: trimmedContent };
  });
}

export function setLastAssistantAgent(
  sessions: Session[],
  sessionId: string,
  agent: string,
  agents?: string[]
): Session[] {
  return updateLastAssistantMessage(sessions, sessionId, (message) => ({
    ...message,
    agent,
    agents: agents || [agent],
  }));
}

export function setLastAssistantStatus(
  sessions: Session[],
  sessionId: string,
  status: string
): Session[] {
  return updateLastAssistantMessage(sessions, sessionId, (message) => ({ ...message, status }));
}

export function setLastAssistantContent(
  sessions: Session[],
  sessionId: string,
  content: string
): Session[] {
  return updateLastAssistantMessage(sessions, sessionId, (message) => ({ ...message, content }));
}

export function appendToolToLastAssistant(
  sessions: Session[],
  sessionId: string,
  tool: NonNullable<Message['tools']>[number]
): Session[] {
  return updateLastAssistantMessage(sessions, sessionId, (message) => ({
    ...message,
    tools: [...(message.tools || []), tool],
  }));
}

export function setLastAssistantAgents(
  sessions: Session[],
  sessionId: string,
  agents: string[]
): Session[] {
  return updateLastAssistantMessage(sessions, sessionId, (message) => ({
    ...message,
    agents,
    agent: agents[agents.length - 1] || message.agent,
  }));
}

export function removeLastTurn(sessions: Session[], sessionId: string): Session[] {
  return sessions.map((session) =>
    session.id === sessionId ? { ...session, messages: session.messages.slice(0, -2) } : session
  );
}

export function removeEmptyAssistantTail(sessions: Session[], sessionId: string): Session[] {
  return sessions.map((session) => {
    if (session.id !== sessionId) return session;

    const lastMessage = session.messages[session.messages.length - 1];
    if (!lastMessage || lastMessage.role !== 'assistant' || lastMessage.content.trim()) {
      return session;
    }

    return { ...session, messages: session.messages.slice(0, -1) };
  });
}
