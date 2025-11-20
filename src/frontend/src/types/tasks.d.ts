export interface ProcessingTask {
  id: string | number;
  file: File;
  fileName: string;
  status: 'pending' | 'processing' | 'completed' | 'error';
  progress: number;
  result?: Blob | null;
  error?: string;
}