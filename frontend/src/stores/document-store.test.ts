import { api } from '@/lib/api';
import { validateFile } from '@/lib/file-validation';
import type { DocumentInfo } from '@/types';
import { useDocumentStore } from './document-store';

vi.mock('@/lib/api', () => ({
  api: {
    getDocuments: vi.fn(),
    deleteDocument: vi.fn(),
    uploadFile: vi.fn(),
  },
}));

vi.mock('@/lib/file-validation', () => ({
  validateFile: vi.fn(),
}));

function resetDocumentStore() {
  useDocumentStore.setState({
    documents: [],
    isUploading: false,
    uploadProgress: 0,
    isLoading: false,
    deletingDocumentIds: [],
    uploadStatus: 'idle',
    uploadError: null,
    documentError: null,
    currentUploadFilename: null,
    currentUploadFileSize: null,
    currentUploadValidation: null,
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const documentInfo: DocumentInfo = {
  id: 'doc-1',
  filename: 'policy.txt',
  file_type: 'text/plain',
  upload_time: '2026-06-13T00:00:00.000Z',
  chunk_count: 2,
  total_tokens: 20,
};

describe('document-store', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    vi.mocked(validateFile).mockResolvedValue({
      isValid: true,
      errors: [],
      warnings: [],
    });
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    resetDocumentStore();
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it('adds an uploaded document to the visible list with parse metadata', async () => {
    vi.useFakeTimers();
    vi.mocked(api.uploadFile).mockResolvedValue({
      document_id: 'doc-uploaded',
      filename: 'policy.txt',
      file_type: 'txt',
      chunks_created: 4,
      total_tokens: 120,
      upload_time: '2026-06-13T00:00:00.000Z',
      status: 'success',
      message: 'ok',
      parse_summary: {
        page_count: 2,
        table_count: 1,
        element_count: 5,
        parent_chunk_count: 2,
        child_chunk_count: 2,
        warnings: ['Page 2 has little extractable text'],
      },
      warnings: ['Page 2 has little extractable text'],
    });
    const file = new File(['hello'], 'policy.txt', { type: 'text/plain' });

    await useDocumentStore.getState().uploadFile(file, 'session-1', 'device-1');

    expect(api.uploadFile).toHaveBeenCalledWith(file, 'session-1', 'device-1', {
      originalName: 'policy.txt',
      size: '5',
      type: 'text/plain',
    });
    expect(useDocumentStore.getState().documents).toEqual([
      {
        id: 'doc-uploaded',
        filename: 'policy.txt',
        file_type: 'txt',
        upload_time: '2026-06-13T00:00:00.000Z',
        chunk_count: 4,
        total_tokens: 120,
        parent_chunk_count: 2,
        child_chunk_count: 2,
        page_count: 2,
        table_count: 1,
        warnings: ['Page 2 has little extractable text'],
      },
    ]);
    expect(useDocumentStore.getState().uploadStatus).toBe('completed');
    expect(useDocumentStore.getState().isUploading).toBe(false);

    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('fetches documents with device and session scope', async () => {
    vi.mocked(api.getDocuments).mockResolvedValue({ documents: [documentInfo] });

    await useDocumentStore.getState().fetchDocuments('device-1', 'session-1');

    expect(api.getDocuments).toHaveBeenCalledWith('device-1', 'session-1');
    expect(useDocumentStore.getState().documents).toEqual([documentInfo]);
    expect(useDocumentStore.getState().documentError).toBeNull();
    expect(useDocumentStore.getState().isLoading).toBe(false);
  });

  it('records fetch errors without clearing the current document list', async () => {
    useDocumentStore.setState({ documents: [documentInfo] });
    vi.mocked(api.getDocuments).mockRejectedValue(new Error('network down'));

    await useDocumentStore.getState().fetchDocuments('device-1', 'session-1');

    expect(useDocumentStore.getState().documents).toEqual([documentInfo]);
    expect(useDocumentStore.getState().documentError).toBe('network down');
    expect(useDocumentStore.getState().isLoading).toBe(false);
  });

  it('tracks deleting documents and removes them after success', async () => {
    const pendingDelete = deferred<void>();
    useDocumentStore.setState({ documents: [documentInfo] });
    vi.mocked(api.deleteDocument).mockReturnValue(pendingDelete.promise);

    const deletePromise = useDocumentStore
      .getState()
      .deleteDocument('doc-1', 'device-1', 'session-1');

    expect(api.deleteDocument).toHaveBeenCalledWith('doc-1', 'device-1', 'session-1');
    expect(useDocumentStore.getState().deletingDocumentIds).toEqual(['doc-1']);

    pendingDelete.resolve();
    await deletePromise;

    expect(useDocumentStore.getState().documents).toEqual([]);
    expect(useDocumentStore.getState().deletingDocumentIds).toEqual([]);
    expect(useDocumentStore.getState().documentError).toBeNull();
  });

  it('clears deleting state and preserves documents after delete failure', async () => {
    useDocumentStore.setState({ documents: [documentInfo] });
    vi.mocked(api.deleteDocument).mockRejectedValue(new Error('delete failed'));

    await expect(
      useDocumentStore.getState().deleteDocument('doc-1', 'device-1', 'session-1')
    ).rejects.toThrow('delete failed');

    expect(useDocumentStore.getState().documents).toEqual([documentInfo]);
    expect(useDocumentStore.getState().deletingDocumentIds).toEqual([]);
    expect(useDocumentStore.getState().documentError).toBe('delete failed');
  });
});
