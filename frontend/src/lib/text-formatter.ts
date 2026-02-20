/**
 * LLM 출력 텍스트 정제 모듈
 * 문맥 기반 텍스트 처리
 */

interface TextSegment {
  type: 'text' | 'list' | 'heading' | 'code' | 'break';
  content: string;
  level?: number;
}

// 한글 문장 종결어미 패턴 (우선순위: 긴 패턴 먼저)
const KOREAN_ENDINGS = ['습니다', '입니다', '있습니다', '없습니다', '됩니다', '했습니다', '하면', '하여', '되어', '함', '등'];

/**
 * 문장을 의미 단위로 분리
 */
function segmentText(text: string): TextSegment[] {
  const segments: TextSegment[] = [];
  const lines = text.split('\n');

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      segments.push({ type: 'break', content: '' });
      continue;
    }

    if (/^[-*•‣○◦▸▹▪▫]\s/.test(trimmed) || /^\d+\.\s/.test(trimmed)) {
      segments.push({ type: 'list', content: trimmed });
      continue;
    }

    if (/^#{1,6}\s/.test(trimmed)) {
      segments.push({ type: 'heading', content: trimmed, level: trimmed.match(/^#+/)?.[0].length });
      continue;
    }

    if (/^```/.test(trimmed)) {
      segments.push({ type: 'code', content: trimmed });
      continue;
    }

    const sentences = splitSentences(trimmed);
    for (const sentence of sentences) {
      segments.push({ type: 'text', content: sentence });
    }
  }

  return segments;
}

/**
 * 문장 단위로 분리
 */
function splitSentences(text: string): string[] {
  const sentences: string[] = [];
  let current = '';

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const nextChar = text[i + 1];

    current += char;

    // 문장 끝 패턴 확인
    const endingInfo = getSentenceEnding(current);

    if (endingInfo && nextChar && !/[\s\n]/.test(nextChar)) {
      // 마침표 뒤 소문자는 소수점 가능성
      if (endingInfo.type === 'punct' && /[a-z]/.test(nextChar)) {
        continue;
      }

      sentences.push(current.trim());
      current = '';
    }
  }

  if (current.trim()) {
    sentences.push(current.trim());
  }

  // 후처리: 단일 마침표 항목을 이전 문장에 붙이기
  return mergeOrphanPunctuation(sentences);
}

/**
 * 문장 끝인지 확인하고 종류 반환
 */
function getSentenceEnding(current: string): { type: 'korean' | 'punct' } | null {
  // 1. 마침표/물음표/느낌표 확인
  if (/[.!?。！？]$/.test(current)) {
    // 한글 종결어미 직후의 마침표는 그 종결어미의 일부로 처리
    const beforePunct = current.slice(0, -1);
    for (const ending of KOREAN_ENDINGS) {
      if (beforePunct.endsWith(ending)) {
        // "입니다." 상황 - "입니다"에서 이미 처리됨
        return null;
      }
    }
    return { type: 'punct' };
  }

  // 2. 한글 종결어미 확인
  for (const ending of KOREAN_ENDINGS) {
    if (current.endsWith(ending)) {
      const beforeEnding = current.slice(0, -ending.length);
      // 종결어미 앞이 공백이나 한글로 끝나야 함
      if (beforeEnding.length === 0 || /[\s가-힣]$/.test(beforeEnding)) {
        return { type: 'korean' };
      }
    }
  }

  return null;
}

/**
 * 단일 마침표/쉼표 항목을 이전 문장에 병합
 */
function mergeOrphanPunctuation(sentences: string[]): string[] {
  const result: string[] = [];

  for (const sentence of sentences) {
    if (result.length === 0) {
      result.push(sentence);
      continue;
    }

    // 단일 문장부호만 있는 항목은 이전 문장에 붙이기
    if (/^[.!?。！？]+$/.test(sentence)) {
      result[result.length - 1] += sentence;
    } else {
      result.push(sentence);
    }
  }

  return result;
}

/**
 * 세그먼트 재조합
 */
function joinSegments(segments: TextSegment[]): string {
  const result: string[] = [];
  let prevType: string | null = null;

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const nextSeg = segments[i + 1];

    switch (seg.type) {
      case 'break':
        if (result.length > 0 && result[result.length - 1] !== '') {
          result.push('');
        }
        break;

      case 'list':
        if (prevType !== 'list' && prevType !== 'break' && result.length > 0) {
          result.push('');
        }
        result.push(seg.content);
        break;

      case 'heading':
        if (result.length > 0 && result[result.length - 1] !== '') {
          result.push('');
        }
        result.push(seg.content);
        if (nextSeg && nextSeg.type !== 'break') {
          result.push('');
        }
        break;

      case 'text':
        if (prevType === 'list' || prevType === 'heading') {
          result.push('');
        }
        result.push(fixSpacingInSentence(seg.content));
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

  return result
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/**
 * 문장 내 공백 처리
 */
function fixSpacingInSentence(text: string): string {
  return text
    // 1. 마침표/물음표/느낌표 앞의 공백 제거 ("입니다 ." -> "입니다.")
    .replace(/\s+([.!?。！？])/g, '$1')
    // 2. 마침표 뒤에 문자가 오면 공백 추가 ("입니다.다음" -> "입니다. 다음")
    .replace(/([.!?。！？])([가-힣A-Z])/g, '$1 $2')
    // 3. 한글 종결어미 뒤에 문자가 오면 공백 추가 ("입니다다음" -> "입니다 다음")
    .replace(/(습니다|입니다|함|등|있습니다|없습니다|됩니다|했습니다|하면|하여|되어)([가-힣A-Z])/g, '$1 $2')
    // 4. 한글 용언과 조사 사이 공백 제거 ("포함 하는" -> "포함하는")
    .replace(/([가-힣])\s+(는|은|이|가|을|를|와|과|로|으로|의|에|에서|부터|까지|와|과)(?=[\s\n]|$)/g, '$1$2')
    // 5. 보조 동사/형용사 붙여쓰기 ("포함 되어" -> "포함되어", "제공 합니다" -> "제공합니다")
    .replace(/([가-힣])\s+(되어|하여|되어서|하면서|하기|함으로|되며|하며|되고|하고|되어야|해야|되면|하면|됩니다|합니다|됨|함)(?=[\s\n.!?]|$)/g, '$1$2');
}

/**
 * 메인 포맷팅 함수
 */
export function formatLLMOutput(text: string): string {
  if (!text || typeof text !== 'string') return text;

  // DEBUG: Log input
  if (process.env.NODE_ENV === 'development') {
    console.log('[DEBUG formatLLMOutput] Input:', JSON.stringify(text.slice(0, 150)));
  }

  const segments = segmentText(text);

  // DEBUG: Log segments
  if (process.env.NODE_ENV === 'development') {
    console.log('[DEBUG formatLLMOutput] Segments count:', segments.length);
    console.log('[DEBUG formatLLMOutput] First few segments:', segments.slice(0, 3).map(s => ({ type: s.type, content: s.content.slice(0, 50) })));
  }

  const result = joinSegments(segments);

  // DEBUG: Log output
  if (process.env.NODE_ENV === 'development') {
    console.log('[DEBUG formatLLMOutput] Output:', JSON.stringify(result.slice(0, 150)));
  }

  return result;
}

/**
 * 참고 문서 섹션 분리
 */
export function separateReferences(text: string): { content: string; references?: string } {
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
  const { content, references } = separateReferences(rawText);
  const formattedContent = formatLLMOutput(content);

  return {
    content: formattedContent,
    references: references ? formatLLMOutput(references) : undefined,
  };
}
