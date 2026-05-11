import {
  addTurnToSession,
  appendAssistantContent,
  createChatTurn,
  generateChatTitle,
  removeEmptyAssistantTail,
} from './chat-turn';
import type { Session } from '@/types';

describe('chat turn helpers', () => {
  test('generates readable title without markdown noise', () => {
    expect(generateChatTitle('## 제목 `code` [link](https://example.com)')).toBe('제목 link');
  });

  test('adds a user and assistant turn to a session', () => {
    const session: Session = {
      id: 's1',
      title: 'New Chat',
      messages: [],
      createdAt: new Date(),
    };
    const { userMessage, assistantMessage } = createChatTurn('hello world');

    const [updated] = addTurnToSession([session], 's1', 'hello world', userMessage, assistantMessage);

    expect(updated.title).toBe('hello world');
    expect(updated.messages).toHaveLength(2);
    expect(updated.messages[0].role).toBe('user');
    expect(updated.messages[1].role).toBe('assistant');
  });

  test('appends content only to the last assistant message', () => {
    const session: Session = {
      id: 's1',
      title: 'Chat',
      createdAt: new Date(),
      messages: [
        { id: 'u1', role: 'user', content: 'hi', createdAt: new Date() },
        { id: 'a1', role: 'assistant', content: 'hel', createdAt: new Date() },
      ],
    };

    const [updated] = appendAssistantContent([session], 's1', 'lo');

    expect(updated.messages[1].content).toBe('hello');
  });

  test('removes empty assistant tail on cancelled stream', () => {
    const session: Session = {
      id: 's1',
      title: 'Chat',
      createdAt: new Date(),
      messages: [
        { id: 'u1', role: 'user', content: 'hi', createdAt: new Date() },
        { id: 'a1', role: 'assistant', content: '', createdAt: new Date() },
      ],
    };

    const [updated] = removeEmptyAssistantTail([session], 's1');

    expect(updated.messages).toHaveLength(1);
  });
});
