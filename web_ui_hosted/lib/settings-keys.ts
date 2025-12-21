/**
 * Centralized constants for web_settings keys to prevent typos.
 * This file mirrors the Python SettingsKeys class in src/config/web_config.py.
 * Keep in sync with the Python version when adding new settings.
 */

export const SettingsKeys = {
  ContentFiltering: {
    CATEGORY: "content_filtering",
    SCORE_THRESHOLD: "score_threshold",
    MAX_EPISODES_PER_DIGEST: "max_episodes_per_digest",
    MIN_EPISODES_PER_DIGEST: "min_episodes_per_digest",
  },

  AudioProcessing: {
    CATEGORY: "audio_processing",
    CHUNK_DURATION_MINUTES: "chunk_duration_minutes",
    TRANSCRIBE_ALL_CHUNKS: "transcribe_all_chunks",
    MAX_CHUNKS_PER_EPISODE: "max_chunks_per_episode",
  },

  Pipeline: {
    CATEGORY: "pipeline",
    MAX_EPISODES_PER_RUN: "max_episodes_per_run",
    DISCOVERY_LOOKBACK_DAYS: "discovery_lookback_days",
  },

  Retention: {
    CATEGORY: "retention",
    LOCAL_MP3_DAYS: "local_mp3_days",
    AUDIO_CACHE_DAYS: "audio_cache_days",
    AUDIO_CHUNKS_DAYS: "audio_chunks_days",
    LOGS_DAYS: "logs_days",
    EPISODE_RETENTION_DAYS: "episode_retention_days",
    DIGEST_RETENTION_DAYS: "digest_retention_days",
    GITHUB_RELEASES_DAYS: "github_releases_days",
  },

  TopicTracking: {
    CATEGORY: "topic_tracking",
    MIN_SCORE_FOR_EXTRACTION: "min_score_for_extraction",
    MAX_TOPICS_PER_EPISODE: "max_topics_per_episode",
    RETENTION_DAYS: "retention_days",
    EXTRACTION_MODEL: "extraction_model",
  },

  AdFiltering: {
    CATEGORY: "ad_filtering",
    ENABLED: "enabled",
    CONFIDENCE_THRESHOLD: "confidence_threshold",
  },

  TopicEvolution: {
    CATEGORY: "topic_evolution",
    ENABLE_NOVELTY_DETECTION: "enable_novelty_detection",
    NOVELTY_THRESHOLD: "novelty_threshold",
    EMBEDDING_MODEL: "embedding_model",
    SIMILARITY_THRESHOLD: "similarity_threshold",
  },

  AIContentScoring: {
    CATEGORY: "ai_content_scoring",
    MODEL: "model",
    MAX_TOKENS: "max_tokens",
    MAX_EPISODES_PER_BATCH: "max_episodes_per_batch",
    MAX_INPUT_TOKENS: "max_input_tokens",
    PROMPT_MAX_CHARS: "prompt_max_chars",
  },

  AIDigestGeneration: {
    CATEGORY: "ai_digest_generation",
    MODEL: "model",
    MAX_OUTPUT_TOKENS: "max_output_tokens",
    MAX_INPUT_TOKENS: "max_input_tokens",
    TRANSCRIPT_BUFFER_PERCENT: "transcript_buffer_percent",
    TRANSCRIPT_MIN_CHARS: "transcript_min_chars",
    TRANSCRIPT_MAX_CHARS: "transcript_max_chars",
  },

  AIMetadataGeneration: {
    CATEGORY: "ai_metadata_generation",
    MODEL: "model",
    MAX_INPUT_TOKENS: "max_input_tokens",
    MAX_TITLE_TOKENS: "max_title_tokens",
    MAX_SUMMARY_TOKENS: "max_summary_tokens",
    MAX_DESCRIPTION_TOKENS: "max_description_tokens",
  },

  AITTSGeneration: {
    CATEGORY: "ai_tts_generation",
    MODEL: "model",
    MAX_CHARACTERS: "max_characters",
  },

  AISTTTranscription: {
    CATEGORY: "ai_stt_transcription",
    MODEL: "model",
    MAX_FILE_SIZE_MB: "max_file_size_mb",
  },

  TranscriptProcessing: {
    CATEGORY: "transcript_processing",
    AD_TRIM_ENABLED: "ad_trim_enabled",
    AD_TRIM_START_PERCENT: "ad_trim_start_percent",
    AD_TRIM_END_PERCENT: "ad_trim_end_percent",
  },
} as const;

// Type helper for strongly-typed category access
export type SettingsCategory = typeof SettingsKeys[keyof typeof SettingsKeys]["CATEGORY"];

/**
 * Setting value types mapped from Python schema types
 */
export type SettingType = 'string' | 'int' | 'float' | 'bool';

/**
 * Union type for all possible setting values
 */
export type SettingValue = string | number | boolean;

/**
 * Schema metadata for a single setting
 */
export interface SettingMeta {
  type: SettingType;
  default: SettingValue;
  min?: number | null;
  max?: number | null;
}

/**
 * Full settings schema structure - matches SETTINGS_SCHEMA in api/settings/schema/route.ts
 */
export interface SettingsSchemaType {
  content_filtering: {
    score_threshold: SettingMeta;
    max_episodes_per_digest: SettingMeta;
    min_episodes_per_digest: SettingMeta;
  };
  audio_processing: {
    chunk_duration_minutes: SettingMeta;
    transcribe_all_chunks: SettingMeta;
    max_chunks_per_episode: SettingMeta;
  };
  pipeline: {
    max_episodes_per_run: SettingMeta;
    discovery_lookback_days: SettingMeta;
  };
  retention: {
    local_mp3_days: SettingMeta;
    audio_cache_days: SettingMeta;
    audio_chunks_days: SettingMeta;
    logs_days: SettingMeta;
    episode_retention_days: SettingMeta;
    digest_retention_days: SettingMeta;
    github_releases_days: SettingMeta;
  };
  topic_tracking: {
    min_score_for_extraction: SettingMeta;
    max_topics_per_episode: SettingMeta;
    retention_days: SettingMeta;
    extraction_model: SettingMeta;
  };
  ad_filtering: {
    enabled: SettingMeta;
    confidence_threshold: SettingMeta;
  };
  topic_evolution: {
    enable_novelty_detection: SettingMeta;
    novelty_threshold: SettingMeta;
    embedding_model: SettingMeta;
    similarity_threshold: SettingMeta;
  };
  ai_content_scoring: {
    model: SettingMeta;
    max_tokens: SettingMeta;
    max_episodes_per_batch: SettingMeta;
    max_input_tokens: SettingMeta;
    prompt_max_chars: SettingMeta;
  };
  ai_digest_generation: {
    model: SettingMeta;
    max_output_tokens: SettingMeta;
    max_input_tokens: SettingMeta;
    transcript_buffer_percent: SettingMeta;
    transcript_min_chars: SettingMeta;
    transcript_max_chars: SettingMeta;
  };
  ai_metadata_generation: {
    model: SettingMeta;
    max_input_tokens: SettingMeta;
    max_title_tokens: SettingMeta;
    max_summary_tokens: SettingMeta;
    max_description_tokens: SettingMeta;
  };
  ai_tts_generation: {
    model: SettingMeta;
    max_characters: SettingMeta;
  };
  ai_stt_transcription: {
    model: SettingMeta;
    max_file_size_mb: SettingMeta;
  };
  transcript_processing: {
    ad_trim_enabled: SettingMeta;
    ad_trim_start_percent: SettingMeta;
    ad_trim_end_percent: SettingMeta;
  };
  database: {
    pool_size: SettingMeta;
    max_overflow: SettingMeta;
    pool_recycle_seconds: SettingMeta;
  };
  api_timeouts: {
    openai_timeout: SettingMeta;
    elevenlabs_timeout: SettingMeta;
    elevenlabs_dialogue_timeout: SettingMeta;
    github_timeout: SettingMeta;
    github_upload_timeout: SettingMeta;
    http_default_timeout: SettingMeta;
    ffmpeg_timeout: SettingMeta;
    audio_download_timeout: SettingMeta;
  };
  tts: {
    rate_limit_delay: SettingMeta;
  };
  discovery: {
    max_entries_per_feed: SettingMeta;
    max_story_arcs_context: SettingMeta;
  };
}

/**
 * Settings values structure - same categories/keys but with actual values instead of SettingMeta
 */
export type SettingsValues = {
  [K in keyof SettingsSchemaType]: {
    [P in keyof SettingsSchemaType[K]]: SettingValue;
  };
};

/**
 * Partial settings values for incremental updates
 */
export type PartialSettingsValues = Partial<{
  [K in keyof SettingsSchemaType]: Partial<{
    [P in keyof SettingsSchemaType[K]]: SettingValue;
  }>;
}>;
