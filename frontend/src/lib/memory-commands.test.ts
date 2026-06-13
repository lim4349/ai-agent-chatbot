import { describe, expect, it } from 'vitest';
import { getCommandFeedbackMessage, parseMemoryCommand } from './memory-commands';

describe('parseMemoryCommand', () => {
  it('does not treat document summary requests as local memory commands', () => {
    expect(parseMemoryCommand('요약해줘').type).toBe('none');
    expect(parseMemoryCommand('업로드 문서 요약해줘').type).toBe('none');
    expect(parseMemoryCommand('IEEE 논문 요약해줘').type).toBe('none');
  });

  it('keeps explicit conversation summary feedback', () => {
    const command = parseMemoryCommand('지금까지 대화 요약해줘');

    expect(command.type).toBe('summarize');
    expect(getCommandFeedbackMessage(command)).toBe('대화를 요약했습니다');
  });
});
