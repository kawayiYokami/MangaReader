/**
 * Uploads a manga file for translation and returns the translated file as a Blob.
 * @param file The file to translate.
 * @param options Translation options.
 * @returns A promise that resolves with the translated file Blob.
 */
export async function translateFile(file: File, options: { targetLang: string }): Promise<Blob> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('target_lang', options.targetLang);

  const response = await fetch('/api/translation/translate-file-and-download', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown server error' }));
    throw new Error(errorData.detail || 'Failed to translate file');
  }

  return response.blob();
}