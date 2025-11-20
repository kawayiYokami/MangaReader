/**
 * Determines the API base URL based on the environment.
 * In development, it's an empty string to allow the Vite proxy to work.
 * In production, it reads from the .env.production file.
 */
export const API_BASE_URL = import.meta.env.PROD
  ? import.meta.env.VITE_API_BASE_URL
  : '';