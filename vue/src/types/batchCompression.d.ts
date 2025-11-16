export interface BatchCompressionTask {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'cancelled' | 'failed';
  total_files: number;
  processed_files: number;
  successful_files: number;
  failed_files: number;
  progress: number;
  current_file: string;
  start_time?: number;
  end_time?: number;
  error_message?: string;
  duration?: number;
  results: Array<{
    original_path: string;
    compressed_path?: string;
    success: boolean;
    error_message?: string;
    compression_ratio?: number;
  }>;
}
