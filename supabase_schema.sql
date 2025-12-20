-- ==============================================================================
-- CANONICAL SCHEMA CONTRACT - SUPABASE/POSTGRESQL
-- ==============================================================================
-- This file is the single source of truth for the database schema.
--
-- Both data access layers (Python SQLAlchemy and TypeScript Supabase JS) must
-- align with this schema.
--
-- Database: PostgreSQL via Supabase
-- Last Updated: 2025-12-20
-- Aligned with: SQLAlchemy models in src/database/sqlalchemy_models.py
--
-- Schema Management:
--   - Changes are made via Alembic migrations: alembic/versions/
--   - Run migrations: python3 -m alembic upgrade head
--   - Check status: python3 -m alembic current
--
-- Row Level Security (RLS):
--   - All tables have RLS enabled
--   - service_role has full CRUD access
--   - authenticated role has read access where applicable
--
-- GitHub Issue #9: Consolidate data access on Supabase
-- ==============================================================================

BEGIN;

-- Alembic version tracking (DO NOT MODIFY MANUALLY)
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- ==============================================================================
-- CORE TABLES
-- ==============================================================================

-- RSS podcast feeds being monitored
CREATE TABLE feeds (
    id SERIAL NOT NULL,
    feed_url VARCHAR(2048) NOT NULL,
    title VARCHAR(512) NOT NULL,
    description TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_checked TIMESTAMP WITHOUT TIME ZONE,
    last_episode_date TIMESTAMP WITHOUT TIME ZONE,
    total_episodes_processed INTEGER NOT NULL DEFAULT 0,
    total_episodes_failed INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id),
    UNIQUE (feed_url)
);

CREATE INDEX ix_feeds_active ON feeds (active);

-- Individual podcast episodes and their processing status
CREATE TABLE episodes (
    id SERIAL NOT NULL,
    episode_guid VARCHAR(1024) NOT NULL,
    feed_id INTEGER NOT NULL,
    title VARCHAR(1024) NOT NULL,
    published_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    audio_url VARCHAR(4096) NOT NULL,
    duration_seconds INTEGER,
    description TEXT,
    audio_path VARCHAR(4096),
    audio_downloaded_at TIMESTAMP WITHOUT TIME ZONE,
    transcript_path VARCHAR(4096),
    transcript_content TEXT,  -- Added in v1.52 for database-stored transcripts
    transcript_generated_at TIMESTAMP WITHOUT TIME ZONE,
    transcript_word_count INTEGER,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    scores JSONB,  -- { topic_slug: float } mapping
    scored_at TIMESTAMP WITHOUT TIME ZONE,
    status VARCHAR(64) NOT NULL DEFAULT 'pending',  -- pending, processing, transcribed, scored, digested, failed
    failure_count INTEGER NOT NULL DEFAULT 0,
    failure_reason TEXT,
    last_failure_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id),
    UNIQUE (episode_guid)
);

CREATE INDEX ix_episodes_status_published ON episodes (status, published_date);
CREATE INDEX ix_episodes_scored ON episodes (scored_at);

-- Generated topic-based daily digests
CREATE TABLE digests (
    id SERIAL NOT NULL,
    topic VARCHAR(256) NOT NULL,
    digest_date DATE NOT NULL,
    digest_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),  -- Added for multiple digests per day
    script_path VARCHAR(4096),
    script_content TEXT,  -- Database-stored script content
    script_word_count INTEGER,
    mp3_path VARCHAR(4096),
    mp3_duration_seconds INTEGER,
    mp3_title VARCHAR(1024),
    mp3_summary TEXT,
    episode_ids JSONB,  -- [int] array of episode IDs
    episode_count INTEGER NOT NULL DEFAULT 0,
    average_score INTEGER,
    github_url VARCHAR(4096),
    published_at TIMESTAMP WITHOUT TIME ZONE,
    generated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'draft',  -- draft, generated, audio_generated, published
    PRIMARY KEY (id),
    CONSTRAINT uq_digests_topic_date_timestamp UNIQUE (topic, digest_date, digest_timestamp)
);

CREATE INDEX ix_digests_date ON digests (digest_date);
CREATE INDEX ix_digests_timestamp ON digests (digest_timestamp);

-- ==============================================================================
-- TOPIC CONFIGURATION
-- ==============================================================================

-- Topic definitions with voice settings and instructions
CREATE TABLE topics (
    id SERIAL NOT NULL,
    slug VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    voice_id VARCHAR(255),  -- ElevenLabs voice ID
    voice_settings JSONB,   -- ElevenLabs voice parameters
    instructions_md TEXT,   -- GPT prompt instructions
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    last_generated_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    -- Multi-voice dialogue support (v1.79+)
    use_dialogue_api BOOLEAN NOT NULL DEFAULT FALSE,
    dialogue_model VARCHAR(50) NOT NULL DEFAULT 'eleven_turbo_v2_5',
    voice_config JSONB,  -- {"speaker_1": {"name": "...", "voice_id": "..."}, "speaker_2": {...}}
    -- Topic tracking support (v1.100+)
    enable_topic_tracking BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_topics_slug UNIQUE (slug),
    PRIMARY KEY (id)
);

CREATE INDEX ix_topics_active ON topics (is_active);
CREATE INDEX ix_topics_sort ON topics (sort_order);

-- Version history for topic instructions
CREATE TABLE topic_instruction_versions (
    id SERIAL NOT NULL,
    topic_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    instructions_md TEXT NOT NULL,
    change_note TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255),
    CONSTRAINT uq_topic_instruction_version UNIQUE (topic_id, version),
    PRIMARY KEY (id)
);

CREATE INDEX ix_topic_instruction_topic ON topic_instruction_versions (topic_id);

-- ==============================================================================
-- DIGEST-EPISODE RELATIONSHIPS
-- ==============================================================================

-- Links between digests and their source episodes
CREATE TABLE digest_episode_links (
    id SERIAL NOT NULL,
    digest_id INTEGER NOT NULL,
    episode_id INTEGER NOT NULL,
    topic VARCHAR(256),
    score DOUBLE PRECISION,
    position INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_digest_episode UNIQUE (digest_id, episode_id),
    PRIMARY KEY (id)
);

CREATE INDEX ix_digest_episode_digest ON digest_episode_links (digest_id);
CREATE INDEX ix_digest_episode_episode ON digest_episode_links (episode_id);

-- ==============================================================================
-- PIPELINE MONITORING
-- ==============================================================================

-- Pipeline run metadata for dashboard
CREATE TABLE pipeline_runs (
    id VARCHAR(64) NOT NULL,
    workflow_run_id BIGINT,
    workflow_name VARCHAR(255),
    trigger VARCHAR(128),
    status VARCHAR(64),
    conclusion VARCHAR(64),
    started_at TIMESTAMP WITHOUT TIME ZONE,
    finished_at TIMESTAMP WITHOUT TIME ZONE,
    phase JSONB,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

CREATE INDEX ix_pipeline_runs_started ON pipeline_runs (started_at);
CREATE INDEX ix_pipeline_runs_workflow ON pipeline_runs (workflow_run_id);

-- Pipeline execution logs
CREATE TABLE pipeline_logs (
    id SERIAL NOT NULL,
    run_id VARCHAR(128) NOT NULL,
    phase VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    level VARCHAR(16) NOT NULL,
    logger_name VARCHAR(256) NOT NULL,
    module VARCHAR(256),
    function VARCHAR(256),
    line INTEGER,
    message TEXT NOT NULL,
    extra JSONB,
    PRIMARY KEY (id)
);

CREATE INDEX ix_pipeline_logs_run_phase_time ON pipeline_logs (run_id, phase, timestamp);
CREATE INDEX ix_pipeline_logs_level ON pipeline_logs (level);

-- Persistent error tracking for workflow pattern analysis
CREATE TABLE workflow_errors (
    id SERIAL NOT NULL,
    error_date DATE NOT NULL,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    run_id VARCHAR(128) NOT NULL,
    workflow_run_id BIGINT,
    error_category VARCHAR(64) NOT NULL,
    phase VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'error',
    feed_id INTEGER,
    feed_url VARCHAR(2048),
    error_code VARCHAR(32),
    error_message TEXT NOT NULL,
    error_summary VARCHAR(512),
    extra JSONB,
    source_log_id INTEGER,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

CREATE INDEX ix_workflow_errors_date ON workflow_errors (error_date);
CREATE INDEX ix_workflow_errors_run_id ON workflow_errors (run_id);
CREATE INDEX ix_workflow_errors_category ON workflow_errors (error_category);
CREATE INDEX ix_workflow_errors_phase ON workflow_errors (phase);
CREATE INDEX ix_workflow_errors_feed_id ON workflow_errors (feed_id);

-- ==============================================================================
-- TOPIC TRACKING AND DEDUPLICATION (v2.00+)
-- ==============================================================================

-- Extracted topics from episode transcripts for deduplication
CREATE TABLE episode_topics (
    id SERIAL NOT NULL,
    episode_id INTEGER NOT NULL,
    topic_name VARCHAR(512) NOT NULL,
    topic_slug VARCHAR(255) NOT NULL,
    key_points TEXT[] NOT NULL,  -- Array of key insight strings
    first_mentioned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    last_mentioned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    mention_count INTEGER NOT NULL DEFAULT 1,
    digest_topic VARCHAR(256) NOT NULL,  -- Parent topic (e.g., "AI and Technology")
    relevance_score DOUBLE PRECISION,
    included_in_digest_id INTEGER,  -- NULL until included in a digest
    included_at TIMESTAMP WITHOUT TIME ZONE,
    -- Topic evolution and type classification (v2.01+)
    topic_type VARCHAR(50) NOT NULL DEFAULT 'other',  -- model_release, use_case, personality, etc.
    novelty_score DOUBLE PRECISION NOT NULL DEFAULT 1.0,  -- 0.0-1.0, how novel is this info
    is_update BOOLEAN NOT NULL DEFAULT FALSE,  -- Is this an update to existing topic?
    parent_topic_id INTEGER REFERENCES episode_topics(id) ON DELETE SET NULL,
    evolution_summary TEXT,  -- What changed since parent topic
    first_seen_at TIMESTAMP WITH TIME ZONE,  -- When this topic slug first appeared
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_episode_topics_episode_slug UNIQUE (episode_id, topic_slug),
    PRIMARY KEY (id)
);

CREATE INDEX ix_episode_topics_episode ON episode_topics (episode_id);
CREATE INDEX ix_episode_topics_slug ON episode_topics (topic_slug);
CREATE INDEX ix_episode_topics_digest_topic ON episode_topics (digest_topic);
CREATE INDEX ix_episode_topics_included ON episode_topics (included_in_digest_id);
CREATE INDEX ix_episode_topics_mentioned ON episode_topics (last_mentioned_at);

-- Common advertisement content for filtering
CREATE TABLE common_ads (
    id SERIAL NOT NULL,
    advertiser_name VARCHAR(256) NOT NULL UNIQUE,
    pattern_keywords JSONB NOT NULL,  -- Array of keyword strings
    confidence_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.8,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    first_detected_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    last_detected_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    detection_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

CREATE INDEX ix_common_ads_active ON common_ads (is_active);
CREATE INDEX ix_common_ads_advertiser ON common_ads (advertiser_name);

-- ==============================================================================
-- STORY ARC TRACKING (v2.29+)
-- ==============================================================================

-- Evolving news narratives tracked over time
CREATE TABLE story_arcs (
    id SERIAL NOT NULL,
    arc_name VARCHAR(512) NOT NULL,
    arc_slug VARCHAR(255) NOT NULL UNIQUE,
    functional_category VARCHAR(50) NOT NULL DEFAULT 'other',  -- model_release, regulation, company_strategy, etc.
    digest_topic VARCHAR(256) NOT NULL,  -- Parent topic
    summary TEXT,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    event_count INTEGER NOT NULL DEFAULT 1,
    source_count INTEGER NOT NULL DEFAULT 1,
    included_in_digest_id INTEGER,
    included_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

CREATE INDEX ix_story_arcs_digest_topic ON story_arcs (digest_topic);
CREATE INDEX ix_story_arcs_category ON story_arcs (functional_category);
CREATE INDEX ix_story_arcs_last_updated ON story_arcs (last_updated_at);
CREATE INDEX ix_story_arcs_slug ON story_arcs (arc_slug);

-- Individual events within a story arc timeline
CREATE TABLE story_arc_events (
    id SERIAL NOT NULL,
    story_arc_id INTEGER NOT NULL REFERENCES story_arcs(id) ON DELETE CASCADE,
    event_date TIMESTAMP WITH TIME ZONE NOT NULL,
    event_summary TEXT NOT NULL,
    key_points TEXT[] NOT NULL DEFAULT '{}',
    source_feed_id INTEGER REFERENCES feeds(id) ON DELETE SET NULL,
    source_episode_id INTEGER REFERENCES episodes(id) ON DELETE SET NULL,
    source_episode_guid VARCHAR(512),
    source_name VARCHAR(256),
    perspective VARCHAR(50),  -- positive, negative, neutral, analytical
    relevance_score DOUBLE PRECISION,
    extracted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

CREATE INDEX ix_story_arc_events_arc_id ON story_arc_events (story_arc_id);
CREATE INDEX ix_story_arc_events_date ON story_arc_events (event_date);
CREATE INDEX ix_story_arc_events_episode ON story_arc_events (source_episode_id);

-- ==============================================================================
-- WEB SETTINGS
-- ==============================================================================

-- Web UI configuration settings
CREATE TABLE IF NOT EXISTS web_settings (
    id SERIAL NOT NULL,
    category VARCHAR(128) NOT NULL,
    setting_key VARCHAR(128) NOT NULL,
    setting_value TEXT NOT NULL,
    value_type VARCHAR(32) DEFAULT 'string',  -- string, int, float, bool, json
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_web_settings_category_key UNIQUE (category, setting_key),
    PRIMARY KEY (id)
);

-- ==============================================================================
-- ROW LEVEL SECURITY POLICIES
-- ==============================================================================
-- All tables have RLS enabled. See Alembic migrations for policy definitions.
-- Policies:
--   - service_role_policy: Full CRUD for backend/migrations
--   - authenticated_read_policy: Read-only for web UI (where applicable)

COMMIT;
