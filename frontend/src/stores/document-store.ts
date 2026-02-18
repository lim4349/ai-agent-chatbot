import { create } from 'zustand';
import { api } from '@/lib/api';
import type { DocumentInfo } from '@/types';
import { validateFile, type ValidationResult } from '@/lib/file-validation';

interface DocumentStore {
  documents: DocumentInfo[];
  isUploading: boolean;
  uploadProgress: number;
  isLoading: boolean;
  uploadStatus: 'idle' | 'uploading' | 'processing' | 'completed' | 'error';
  uploadError: string | null;
  currentUploadFilename: string | null;
  currentUploadFileSize: number | null;
  currentUploadValidation: ValidationResult | null;

  uploadFile: (file: File, sessionId: string, deviceId: string) => Promise<void>;
  fetchDocuments: (deviceId: string) => Promise<void>;
  deleteDocument: (id: string, deviceId: string) => Promise<void>;
  resetUploadStatus: () => void;
  clearValidationError: () => void;
}

export const useDocumentStore = create<DocumentStore>()((set, get) => ({
  documents: [],
  isUploading: false,
  uploadProgress: 0,
  isLoading: false,
  uploadStatus: 'idle',
  uploadError: null,
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
      });

      // Add the new document to the list
      const newDoc: DocumentInfo = {
        id: response.document_id,
        filename: response.filename,
        file_type: response.file_type,
        upload_time: response.upload_time,
        chunk_count: response.chunks_created,
        total_tokens: response.total_tokens,
      };

      set((state) => ({
        documents: [newDoc, ...state.documents],
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

  fetchDocuments: async (deviceId: string) => {
    set({ isLoading: true });

    try {
      const response = await api.getDocuments(deviceId);
      set({ documents: response.documents });
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      set({ isLoading: false });
    }
  },

  deleteDocument: async (id: string, deviceId: string) => {
    try {
      await api.deleteDocument(id, deviceId);
      set((state) => ({
        documents: state.documents.filter((doc) => doc.id !== id),
      }));
    } catch (error) {
      console.error('Failed to delete document:', error);
      throw error;
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
