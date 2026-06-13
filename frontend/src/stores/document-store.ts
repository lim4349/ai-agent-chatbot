import { create } from 'zustand';
import { api } from '@/lib/api';
import type { DocumentInfo } from '@/types';
import { validateFile, type ValidationResult } from '@/lib/file-validation';

interface DocumentStore {
  documents: DocumentInfo[];
  isUploading: boolean;
  uploadProgress: number;
  isLoading: boolean;
  deletingDocumentIds: string[];
  uploadStatus: 'idle' | 'uploading' | 'processing' | 'completed' | 'error';
  uploadError: string | null;
  documentError: string | null;
  currentUploadFilename: string | null;
  currentUploadFileSize: number | null;
  currentUploadValidation: ValidationResult | null;

  uploadFile: (file: File, sessionId: string, deviceId: string) => Promise<void>;
  fetchDocuments: (deviceId: string, sessionId?: string) => Promise<void>;
  deleteDocument: (id: string, deviceId: string, sessionId?: string) => Promise<void>;
  resetUploadStatus: () => void;
  clearValidationError: () => void;
}

export const useDocumentStore = create<DocumentStore>()((set, get) => ({
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

  uploadFile: async (file: File, sessionId: string, deviceId: string) => {
    // Validate file first
    const validation = await validateFile(file);

    if (!validation.isValid) {
      set({
        uploadStatus: 'error',
        uploadError: 'File validation failed',
        currentUploadFilename: file.name,
        currentUploadFileSize: file.size,
        currentUploadValidation: validation,
      });
      return;
    }

    set({
      isUploading: true,
      uploadProgress: 0,
      uploadStatus: 'uploading',
      uploadError: null,
      currentUploadFilename: file.name,
      currentUploadFileSize: file.size,
      currentUploadValidation: validation,
    });

    // Simulate progress updates
    const progressInterval = setInterval(() => {
      set((state) => ({
        uploadProgress: Math.min(state.uploadProgress + 10, 90),
      }));
    }, 200);

    try {
      set({ uploadStatus: 'processing' });

      const response = await api.uploadFile(file, sessionId, deviceId, {
        originalName: file.name,
        size: file.size.toString(),
        type: file.type,
      });

      clearInterval(progressInterval);

      set({
        uploadProgress: 100,
        uploadStatus: 'completed',
        isUploading: false,
        uploadError: null,
      });

      // Add the new document to the list
      const newDoc: DocumentInfo = {
        id: response.document_id,
        filename: response.filename,
        file_type: response.file_type,
        upload_time: response.upload_time,
        chunk_count: response.chunks_created,
        total_tokens: response.total_tokens,
        parent_chunk_count: response.parse_summary?.parent_chunk_count,
        child_chunk_count: response.parse_summary?.child_chunk_count,
        page_count: response.parse_summary?.page_count,
        table_count: response.parse_summary?.table_count,
        warnings: response.warnings || response.parse_summary?.warnings || [],
      };

      set((state) => ({
        documents: [newDoc, ...state.documents.filter((doc) => doc.id !== newDoc.id)],
      }));

      // Reset status after a delay
      setTimeout(() => {
        get().resetUploadStatus();
      }, 3000);
    } catch (error) {
      clearInterval(progressInterval);

      set({
        uploadProgress: 0,
        uploadStatus: 'error',
        isUploading: false,
        uploadError: error instanceof Error ? error.message : 'Upload failed',
      });
    }
  },

  fetchDocuments: async (deviceId: string, sessionId?: string) => {
    set({ isLoading: true, documentError: null });

    try {
      const response = await api.getDocuments(deviceId, sessionId);
      set({ documents: response.documents, documentError: null });
    } catch (error) {
      console.error('Failed to fetch documents:', error);
      set({
        documentError: error instanceof Error ? error.message : 'Failed to fetch documents',
      });
    } finally {
      set({ isLoading: false });
    }
  },

  deleteDocument: async (id: string, deviceId: string, sessionId?: string) => {
    set((state) => ({
      deletingDocumentIds: [...new Set([...state.deletingDocumentIds, id])],
      documentError: null,
    }));

    try {
      await api.deleteDocument(id, deviceId, sessionId);
      set((state) => ({
        documents: state.documents.filter((doc) => doc.id !== id),
        documentError: null,
      }));
    } catch (error) {
      console.error('Failed to delete document:', error);
      set({
        documentError: error instanceof Error ? error.message : 'Failed to delete document',
      });
      throw error;
    } finally {
      set((state) => ({
        deletingDocumentIds: state.deletingDocumentIds.filter((documentId) => documentId !== id),
      }));
    }
  },

  resetUploadStatus: () => {
    set({
      uploadStatus: 'idle',
      uploadProgress: 0,
      uploadError: null,
      currentUploadFilename: null,
      currentUploadFileSize: null,
      currentUploadValidation: null,
    });
  },

  clearValidationError: () => {
    set({
      uploadStatus: 'idle',
      uploadError: null,
      currentUploadValidation: null,
    });
  },
}));
