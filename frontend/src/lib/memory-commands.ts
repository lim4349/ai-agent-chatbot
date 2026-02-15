export type MemoryCommandType = 'remember' | 'recall' | 'forget' | 'summarize' | 'none';

export interface ParsedMemoryCommand {
  type: MemoryCommandType;
  content?: string;
}

/**
 * Parse Korean memory commands from user input
 *
 * Supported commands:
 * - "기억해: 내용" -> { type: 'remember', content: '내용' }
 * - "기억해줘: 내용" -> { type: 'remember', content: '내용' }
 * - "알고 있니?" -> { type: 'recall' }
 * - "알려줘" -> { type: 'recall' }
 * - "잊어줘: 내용" -> { type: 'forget', content: '내용' }
 * - "잊어: 내용" -> { type: 'forget', content: '내용' }
 * - "요약해줘" -> { type: 'summarize' }
 * - "요약해" -> { type: 'summarize' }
 */
export function parseMemoryCommand(message: string): ParsedMemoryCommand {
  const trimmed = message.trim();

  // Remember commands: 기억해:, 기억해줘:
  if (trimmed.startsWith('기억해:') || trimmed.startsWith('기억해줘:')) {
    const content = trimmed
      .replace(/^기억해(줘)?:\s*/, '')
      .trim();
    if (content) {
      return { type: 'remember', content };
    }
  }

  // Recall commands: 알고 있니?, 알려줘, 기억한 것 알려줘
  if (
    trimmed === '알고 있니?' ||
    trimmed === '알고있니?' ||
    trimmed === '알려줘' ||
    trimmed === '기억한 것 알려줘' ||
    trimmed === '기억한거 알려줘' ||
    trimmed === '뭐 기억하고 있어?'
  ) {
    return { type: 'recall' };
  }

  // Forget commands: 잊어줘:, 잊어:
  if (trimmed.startsWith('잊어줘:') || trimmed.startsWith('잊어:')) {
    const content = trimmed
      .replace(/^잊어(줘)?:\s*/, '')
      .trim();
    if (content) {
      return { type: 'forget', content };
    }
  }

  // Summarize commands: 요약해줘, 요약해
  if (
    trimmed === '요약해줘' ||
    trimmed === '요약해' ||
    trimmed === '대화 요약해줘' ||
    trimmed === '대화 요약해'
  ) {
    return { type: 'summarize' };
  }

  return { type: 'none' };
}

/**
 * Get a human-readable description of the command for UI feedback
 */
export function getCommandFeedbackMessage(command: ParsedMemoryCommand): string {
  switch (command.type) {
    case 'remember':
      return '정보를 저장했습니다';
    case 'recall':
      return '저장된 정보를 불러옵니다';
    case 'forget':
      return '정보를 삭제했습니다';
    case 'summarize':
      return '대화를 요약했습니다';
    case 'none':
    default:
      return '';
  }
}

/**
 * Get icon for the command type
 */
export function getCommandIcon(command: ParsedMemoryCommand): string {
  switch (command.type) {
    case 'remember':
      return '';
    case 'recall':
      return '';
    case 'forget':
      return '';
    case 'summarize':
      return '';
    case 'none':
    default:
      return '';
  }
}
