import { renderToStaticMarkup } from 'react-dom/server';
import { ToolUsage } from './tool-usage';

describe('ToolUsage', () => {
  it('renders normalized evidence details', () => {
    const html = renderToStaticMarkup(
      <ToolUsage
        tools={[
          {
            name: 'retriever',
            query: '경조사비',
            confidence: 'high',
            sources: ['policy.pdf'],
            evidenceItems: [
              {
                tool: 'retriever',
                source: 'policy.pdf',
                page: 3,
                page_end: 4,
                heading_path: '제3장 복리후생 > 제2조 경조사비',
                score: 0.91,
                confidence: 'high',
                snippet: '결혼 경조사비는 50만 원입니다.',
              },
            ],
          },
        ]}
      />
    );

    expect(html).toContain('근거 상세');
    expect(html).toContain('policy.pdf');
    expect(html).toContain('3-4페이지');
    expect(html).toContain('제3장 복리후생 &gt; 제2조 경조사비');
    expect(html).toContain('점수');
    expect(html).toContain('0.91');
    expect(html).toContain('결혼 경조사비는 50만 원입니다.');
  });

  it('marks low-confidence evidence', () => {
    const html = renderToStaticMarkup(
      <ToolUsage
        tools={[
          {
            name: 'retriever',
            confidence: 'low',
            evidenceItems: [
              {
                tool: 'retriever',
                source: 'ops-runbook.md',
                score: 0.31,
                confidence: 'low',
                snippet: '관련성이 낮은 근거입니다.',
              },
            ],
          },
        ]}
      />
    );

    expect(html).toContain('aria-label="낮은 신뢰도"');
    expect(html).toContain('border-amber-500');
  });
});
