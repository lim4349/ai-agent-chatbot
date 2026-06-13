import { renderToStaticMarkup } from 'react-dom/server';
import { DocumentList } from './document-list';
import type { DocumentInfo } from '@/types';

const documentInfo: DocumentInfo = {
  id: 'doc-1',
  filename: 'policy.txt',
  file_type: 'text/plain',
  upload_time: '2026-06-13T00:00:00.000Z',
  chunk_count: 2,
  total_tokens: 20,
};
const parsedDocumentInfo: DocumentInfo = {
  ...documentInfo,
  child_chunk_count: 4,
  page_count: 3,
  table_count: 1,
  warnings: ['Page 2 has little extractable text'],
};

describe('DocumentList', () => {
  it('renders loading state', () => {
    const html = renderToStaticMarkup(
      <DocumentList documents={[]} onDelete={() => {}} isLoading />
    );

    expect(html).toContain('문서 목록을 불러오는 중');
  });

  it('renders error state', () => {
    const html = renderToStaticMarkup(
      <DocumentList documents={[]} onDelete={() => {}} isLoading={false} error="boom" />
    );

    expect(html).toContain('문서 목록을 불러오지 못했습니다');
    expect(html).toContain('boom');
  });

  it('renders empty state', () => {
    const html = renderToStaticMarkup(
      <DocumentList documents={[]} onDelete={() => {}} isLoading={false} />
    );

    expect(html).toContain('아직 문서가 없습니다');
  });

  it('renders deleting state for a document', () => {
    const html = renderToStaticMarkup(
      <DocumentList
        documents={[documentInfo]}
        onDelete={() => {}}
        isLoading={false}
        deletingDocumentIds={['doc-1']}
      />
    );

    expect(html).toContain('policy.txt');
    expect(html).toContain('aria-label="삭제 중');
    expect(html).toContain('disabled=""');
  });

  it('renders parse metadata and warning state', () => {
    const html = renderToStaticMarkup(
      <DocumentList documents={[parsedDocumentInfo]} onDelete={() => {}} isLoading={false} />
    );

    expect(html).toContain('3페이지');
    expect(html).toContain('표 1개');
    expect(html).toContain('파싱 경고 1개');
    expect(html).toContain('검색 청크');
  });
});
