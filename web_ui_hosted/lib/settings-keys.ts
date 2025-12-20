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
