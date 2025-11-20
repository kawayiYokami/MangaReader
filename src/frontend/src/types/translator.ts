// file: vue/src/types/translator.ts

export interface APIConfig {
  name: string;
  api_type: string;
  api_key: string;
  model: string;
  temperature: number;
  max_tokens: number;
  api_base_url?: string;
  request_interval_ms: number;
}

export enum TranslationStatus {
  SUCCESS = "success",
  FAILURE = "failure",
  NOT_TRANSLATED = "not_translated",
}

export interface DialogueLine {
  speaker_id: number;
  original_text: string;
  translated_text: string;
}

export interface TranslationScript {
  script: DialogueLine[];
}

export interface ImageTranslationResult {
  image_index: number;
  status: TranslationStatus;
  translation_script?: TranslationScript;
  error_message?: string;
}