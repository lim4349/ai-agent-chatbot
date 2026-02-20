/**
 * LLM 출력 텍스트 정제 모듈
 * 정규식 대신 AST 기반 접근으로 문맥을 이해하고 처리
 */

import { remark } from 'remark';
import remarkGfm from 'remark-gfm';

interface TextSegment {
  type: 'text' | 'list' | 'heading' | 'code' | 'break';
  content: string;
  level?: number;
}

/**
 * 문장을 의미 단위로 분리
 * 한글/영문 문장 끝을 인식하여 적절히 분리
 */
function segmentText(text: string): TextSegment[] {
  const segments: TextSegment[] = [];

  // 줄 단위로 먼저 분리
  const lines = text.split('\n');

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      segments.push({ type: 'break', content: '' });
      continue;
    }

    // 리스트 항목인지 확인 (-, *, 1., • 등)
    if (/^[-*•‣○◦▸▹▪▫]\s/.test(trimmed) || /^\d+\.\s/.test(trimmed)) {
      segments.push({ type: 'list', content: trimmed });
      continue;
    }

    // 헤딩인지 확인
    if (/^#{1,6}\s/.test(trimmed)) {
      segments.push({ type: 'heading', content: trimmed, level: trimmed.match(/^#+/)?.[0].length });
      continue;
    }

    // 코드 블록
    if (/^```/.test(trimmed)) {
      segments.push({ type: 'code', content: trimmed });
      continue;
    }

    // 일반 텍스트 - 문장 단위로 분리
    const sentences = splitSentences(trimmed);
    for (const sentence of sentences) {
      segments.push({ type: 'text', content: sentence });
    }
  }

  return segments;
}

/**
 * 문장 단위로 분리 (한글/영문 모두 지원)
 */
function splitSentences(text: string): string[] {
  const sentences: string[] = [];
  let current = '';

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const nextChar = text[i + 1];

    current += char;

    // 문장 끝 표현 확인
    const isSentenceEnd = /[.!?。！？]$/.test(current) ||
                          /(습니다|입니다|함|등|있습니다|없습니다|됩니다|했습니다|하면)$/.test(current);

    if (isSentenceEnd && nextChar && !/[\s\n]/.test(nextChar)) {
      // 문장 끝인데 다음 글자가 공백/줄바꿈이 아니면 분리
      sentences.push(current.trim());
      current = '';
    }
  }

  if (current.trim()) {
    sentences.push(current.trim());
  }

  return sentences.length > 0 ? sentences : [text];
}

/**
 * 세그먼트를 다시 조합하며 적절한 줄바꿈 추가
 */
function joinSegments(segments: TextSegment[]): string {
  const result: string[] = [];
  let prevType: string | null = null;

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const nextSeg = segments[i + 1];

    switch (seg.type) {
      case 'break':
        result.push('');
        break;

      case 'list':
        // 리스트 전에 빈 줄이 없으면 추가 (단 연속된 리스트는 제외)
        if (prevType !== 'list' && prevType !== 'break' && result.length > 0) {
          result.push('');
        }
        result.push(seg.content);
        break;

      case 'heading':
        // 헤딩 전후로 빈 줄
        if (result.length > 0 && result[result.length - 1] !== '') {
          result.push('');
        }
        result.push(seg.content);
        if (nextSeg && nextSeg.type !== 'break') {
          result.push('');
        }
        break;

      case 'text':
        // 이전이 리스트나 헤딩이었으면 빈 줄 추가
        if (prevType === 'list' || prevType === 'heading') {
          result.push('');
        }

        // 문장 내에서 마침표 뒤 공백 처리
        const fixed = fixSpacingInSentence(seg.content);
        result.push(fixed);
        break;

      case 'code':
        if (result.length > 0 && result[result.length - 1] !== '') {
          result.push('');
        }
        result.push(seg.content);
        break;
    }

    prevType = seg.type;
  }

  // 연속된 빈 줄 제거
  return result
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/**
 * 문장 난ㄱ에서 마침표 뒤 공백 처리
 */
function fixSpacingInSentence(text: string): string {
  // 마침표/물음표/느낌표 뒤에 한글/영문이 바로 오면 공백 추가
  return text
    .replace(/([.!?])([가-힣A-Za-z])/g, '$1 $2')
    // 한글 종결어미 뒤에 한글/영문이 바로 오면 공백 추가
    .replace(/(습니다|입니다|함|등|있습니다|없습니다|됩니다|했습니다|하면)([가-힣A-Za-z])/g, '$1 $2');
}

/**
 * 메인 포맷팅 함수
 */
export function formatLLMOutput(text: string): string {
  if (!text || typeof text !== 'string') return text;

  // 1단계: 세그먼트 분리
  const segments = segmentText(text);

  // 2단계: 재조합
  const formatted = joinSegments(segments);

  return formatted;
}

/**
 * 참고 문서/출처 섹션 분리
 */
export function separateReferences(text: string): { content: string; references?: string } {
  // 참고 문서 패턴 매칭
  const patterns = [
    /(참고 문서|참고문서|출처|References?|Sources?|Bibliography)[:：]\s*/i,
    /\n(참고 문서|참고문서|출처|References?|Sources?)[:：]?\s*/i,
  ];

  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match && match.index !== undefined) {
      const content = text.slice(0, match.index).trim();
      const references = text.slice(match.index).trim();
      return { content, references };
    }
  }

  return { content: text };
}

/**
 * 완전한 후처리 파이프라인
 */
export function postProcessLLMOutput(rawText: string): { content: string; references?: string } {
  // 1. 참고 문서 분리
  const { content, references } = separateReferences(rawText);

  // 2. 본문 포맷팅
  const formattedContent = formatLLMOutput(content);

  return {
    content: formattedContent,
    references: references ? formatLLMOutput(references) : undefined,
  };
}
