// File validation utilities

export const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB in bytes

export const ALLOWED_FILE_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'text/markdown',
  'text/csv',
  'application/json',
] as const;

export const FILE_TYPE_LABELS: Record<string, string> = {
  'application/pdf': 'PDF',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
  'text/plain': 'TXT',
  'text/markdown': 'MD',
  'text/csv': 'CSV',
  'application/json': 'JSON',
};

// File extension to MIME type mapping
export const EXTENSION_TO_MIME: Record<string, string> = {
  '.pdf': 'application/pdf',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  '.txt': 'text/plain',
  '.md': 'text/markdown',
  '.csv': 'text/csv',
  '.json': 'application/json',
};

// Dangerous/suspicious extensions that should be rejected
export const SUSPICIOUS_EXTENSIONS = [
  '.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.msi', '.dll',
  '.vbs', '.vbe', '.js', '.jse', '.ws', '.wsf', '.wsc', '.wsh',
  '.ps1', '.ps1xml', '.ps2', '.ps2xml', '.psc1', '.psc2',
  '.msh', '.msh1', '.msh2', '.mshxml', '.msh1xml', '.msh2xml',
  '.sh', '.bash', '.zsh', '.csh', '.tcsh', '.ksh',
  '.app', '.deb', '.rpm', '.dmg', '.pkg', '.run',
  '.bin', '.o', '.so', '.dylib', '.lib',
  '.jar', '.war', '.ear', '.class',
];

export interface ValidationError {
  code: string;
  message: string;
  severity: 'error' | 'warning';
}

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
}

/**
 * Format file size to human readable string
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Get file extension from filename
 */
export function getFileExtension(filename: string): string {
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
  return ext;
}

/**
 * Validate filename for path traversal and suspicious patterns
 */
export function validateFilename(filename: string): ValidationError | null {
  // Check for path traversal attempts
  if (filename.includes('..') || filename.includes('/') || filename.includes('\\')) {
    return {
      code: 'INVALID_FILENAME',
      message: 'Filename contains invalid characters or path traversal attempts',
      severity: 'error',
    };
  }

  // Check for suspicious extensions
  const ext = getFileExtension(filename);
  if (SUSPICIOUS_EXTENSIONS.includes(ext)) {
    return {
      code: 'SUSPICIOUS_EXTENSION',
      message: `Suspicious file extension: ${ext}`,
      severity: 'error',
    };
  }

  // Check for null bytes
  if (filename.includes('\0')) {
    return {
      code: 'NULL_BYTE',
      message: 'Filename contains null bytes',
      severity: 'error',
    };
  }

  // Check for control characters
  if (/[\x00-\x1f\x7f]/.test(filename)) {
    return {
      code: 'CONTROL_CHARACTERS',
      message: 'Filename contains control characters',
      severity: 'error',
    };
  }

  return null;
}

/**
 * Validate file size
 */
export function validateFileSize(file: File): ValidationError | null {
  if (file.size > MAX_FILE_SIZE) {
    return {
      code: 'FILE_TOO_LARGE',
      message: `File too large (${formatFileSize(file.size)} > ${formatFileSize(MAX_FILE_SIZE)} limit)`,
      severity: 'error',
    };
  }

  if (file.size === 0) {
    return {
      code: 'EMPTY_FILE',
      message: 'File is empty',
      severity: 'error',
    };
  }

  return null;
}

/**
 * Validate file type matches extension
 */
export function validateFileTypeMatchesExtension(file: File): ValidationError | null {
  const ext = getFileExtension(file.name);
  const expectedMime = EXTENSION_TO_MIME[ext];

  if (!expectedMime) {
    return {
      code: 'UNKNOWN_EXTENSION',
      message: `Unknown file extension: ${ext}`,
      severity: 'warning',
    };
  }

  // Check if declared MIME type matches expected
  if (file.type && file.type !== expectedMime) {
    return {
      code: 'MIME_MISMATCH',
      message: `File type (${file.type}) doesn't match extension (${ext})`,
      severity: 'warning',
    };
  }

  return null;
}

/**
 * Validate file type is allowed
 */
export function validateFileTypeAllowed(file: File): ValidationError | null {
  const ext = getFileExtension(file.name);
  const expectedMime = EXTENSION_TO_MIME[ext];

  // Use declared type or expected type from extension
  const fileType = file.type || expectedMime;

  if (!fileType || !ALLOWED_FILE_TYPES.includes(fileType as string)) {
    return {
      code: 'INVALID_TYPE',
      message: `Invalid file type. Allowed: ${Array.from(new Set([...ALLOWED_FILE_TYPES, ...Object.keys(EXTENSION_TO_MIME)]))
        .map(t => FILE_TYPE_LABELS[t] || t)
        .join(', ')}`,
      severity: 'error',
    };
  }

  return null;
}

/**
 * Magic byte signatures for file validation
 */
const MAGIC_BYTES: Record<string, Uint8Array> = {
  // PDF: %PDF
  'application/pdf': new Uint8Array([0x25, 0x50, 0x44, 0x46]),
  // ZIP (DOCX, XLSX, etc.): PK
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': new Uint8Array([0x50, 0x4B, 0x03, 0x04]),
  'application/zip': new Uint8Array([0x50, 0x4B, 0x03, 0x04]),
};

/**
 * Validate file using magic bytes
 */
export async function validateMagicBytes(file: File): Promise<ValidationError | null> {
  const ext = getFileExtension(file.name);
  const expectedMime = EXTENSION_TO_MIME[ext];

  if (!expectedMime || !MAGIC_BYTES[expectedMime]) {
    // No magic bytes defined for this type
    return null;
  }

  try {
    const buffer = await file.slice(0, 4).arrayBuffer();
    const header = new Uint8Array(buffer);
    const expected = MAGIC_BYTES[expectedMime];

    // Compare first 4 bytes
    for (let i = 0; i < expected.length; i++) {
      if (header[i] !== expected[i]) {
        return {
          code: 'MAGIC_MISMATCH',
          message: `File content doesn't match ${FILE_TYPE_LABELS[expectedMime]} format`,
          severity: 'warning',
        };
      }
    }
  } catch (error) {
    // If we can't read the file, just warn
    return {
      code: 'READ_ERROR',
      message: 'Could not verify file content',
      severity: 'warning',
    };
  }

  return null;
}

/**
 * Comprehensive file validation
 */
export async function validateFile(file: File): Promise<ValidationResult> {
  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];

  // Validate filename
  const filenameError = validateFilename(file.name);
  if (filenameError) {
    if (filenameError.severity === 'error') {
      errors.push(filenameError);
    } else {
      warnings.push(filenameError);
    }
  }

  // Validate file size
  const sizeError = validateFileSize(file);
  if (sizeError) {
    if (sizeError.severity === 'error') {
      errors.push(sizeError);
    } else {
      warnings.push(sizeError);
    }
  }

  // Validate file type is allowed
  const typeError = validateFileTypeAllowed(file);
  if (typeError) {
    if (typeError.severity === 'error') {
      errors.push(typeError);
    } else {
      warnings.push(typeError);
    }
  }

  // Validate MIME type matches extension
  const mimeWarning = validateFileTypeMatchesExtension(file);
  if (mimeWarning) {
    warnings.push(mimeWarning);
  }

  // Validate magic bytes (async)
  try {
    const magicWarning = await validateMagicBytes(file);
    if (magicWarning) {
      warnings.push(magicWarning);
    }
  } catch (error) {
    // Magic bytes validation is optional, don't fail if it errors
    console.warn('Magic bytes validation failed:', error);
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  };
}

/**
 * Get file size percentage relative to max size
 */
export function getFileSizePercentage(size: number): number {
  return Math.min((size / MAX_FILE_SIZE) * 100, 100);
}

/**
 * Get file size status
 */
export function getFileSizeStatus(size: number): 'ok' | 'warning' | 'error' {
  const percentage = getFileSizePercentage(size);

  if (percentage >= 100) return 'error';
  if (percentage >= 80) return 'warning';
  return 'ok';
}
