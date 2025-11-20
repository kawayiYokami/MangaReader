/**
 * Uploads a manga file for compression.
 * @param file The file to compress.
 * @param options Compression options.
 * @returns A promise that resolves with the compressed file Blob.
 */
export async function compressFile(file: File, options: { quality: number }): Promise<Blob> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('webp_quality', String(options.quality));

  const response = await fetch('/api/manga/compress-file-and-download', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown server error' }));
    throw new Error(errorData.detail || 'Failed to compress file');
  }

  return response.blob();
}